import asyncio
import operator
import datetime
from typing import List, Optional, Dict, Any, TypedDict, Literal, cast, Callable, Awaitable
from loguru import logger
from langsmith import traceable
import httpx
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from src_v2.config.settings import settings
from src_v2.config.constants import should_use_base64
from src_v2.utils.image_utils import process_image_for_llm
from src_v2.core.character import Character
from src_v2.agents.llm_factory import create_llm
from src_v2.agents.classifier import ComplexityClassifier
from src_v2.agents.reflective_graph import ReflectiveGraphAgent
from src_v2.agents.character_graph import CharacterGraphAgent
from src_v2.agents.context_builder import ContextBuilder
from src_v2.utils.llm_retry import invoke_with_retry, get_image_error_message
from src_v2.safety.output_guard import OutputSafetyGuard
from src_v2.core.database import db_manager
from influxdb_client import Point

# Managers for Context Node
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager

# Define State
class SuperGraphState(TypedDict):
    # Inputs
    user_input: str
    user_id: str
    character: Character
    chat_history: List[BaseMessage]
    context_variables: Dict[str, Any]
    image_urls: Optional[List[str]]
    callback: Optional[Callable[[str], Awaitable[None]]]  # Status callback for reasoning steps
    
    # Internal Processing
    classification: Optional[Dict[str, Any]] # {complexity: str, intents: List[str]}
    context: Optional[Dict[str, Any]] # {memories, facts, trust, goals, evolution, diary, dream, knowledge, known_bots, stigmergy}
    system_prompt: Optional[str]
    
    # Output
    final_response: Optional[str]
    metadata: Optional[Dict[str, Any]]

class MasterGraphAgent:
    """
    The Supergraph: A unified StateGraph that orchestrates the entire request lifecycle.
    Replaces the manual logic in AgentEngine.
    """
    
    def __init__(self):
        self.classifier = ComplexityClassifier()
        self.reflective_agent = ReflectiveGraphAgent()
        self.character_agent = CharacterGraphAgent()
        self.context_builder = ContextBuilder()
        self.fast_llm = create_llm(mode="main") # Use main model for fast path, but without tools
        self.output_guard = OutputSafetyGuard()
        
        # Build Graph
        workflow = StateGraph(SuperGraphState)
        
        # Add Nodes
        workflow.add_node("context_fetcher", self.context_node)
        workflow.add_node("classifier", self.classifier_node)
        workflow.add_node("prompt_builder", self.prompt_builder_node)
        workflow.add_node("reflective_agent", self.reflective_subgraph_node)
        workflow.add_node("character_agent", self.character_subgraph_node)
        workflow.add_node("fast_responder", self.fast_responder_node) # Fallback/Simple
        workflow.add_node("output_guard", self.output_guard_node)
        
        # Edges - Classifier FIRST so extraction can inform context fetch
        workflow.set_entry_point("classifier")
        workflow.add_edge("classifier", "context_fetcher")
        workflow.add_edge("context_fetcher", "prompt_builder")
        
        # Conditional Routing
        workflow.add_conditional_edges(
            "prompt_builder",
            self.router_logic,
            {
                "reflective": "reflective_agent",
                "character": "character_agent",
                "fast": "fast_responder"
            }
        )
        
        # Route all responses through output guard
        workflow.add_edge("reflective_agent", "output_guard")
        workflow.add_edge("character_agent", "output_guard")
        workflow.add_edge("fast_responder", "output_guard")
        workflow.add_edge("output_guard", END)
        
        self.graph = workflow.compile()

    async def output_guard_node(self, state: SuperGraphState) -> SuperGraphState:
        """Audits response for safety if high-risk behavior detected."""
        return await self.output_guard.check(state)

    async def _log_metrics(self, user_id: Optional[str], character_name: str, latency: float, mode: str, complexity: Any):
        """Logs response metrics to InfluxDB."""
        if db_manager.influxdb_write_api:
            try:
                # Handle complexity=False case
                complexity_str = str(complexity) if complexity else "simple"
                safe_user_id = user_id or "unknown"

                point = Point("response_metrics") \
                    .tag("user_id", safe_user_id) \
                    .tag("bot_name", character_name) \
                    .tag("mode", mode) \
                    .tag("complexity", complexity_str) \
                    .field("latency", float(latency)) \
                    .time(datetime.datetime.utcnow())
                
                db_manager.influxdb_write_api.write(
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG,
                    record=point
                )
                logger.debug(f"Logged metrics to InfluxDB: latency={latency:.2f}s mode={mode}")
            except Exception as e:
                logger.error(f"Failed to log metrics to InfluxDB: {e}")
        else:
            logger.warning("InfluxDB write API not available, skipping metrics logging")

    async def context_node(self, state: SuperGraphState):
        """Parallel fetch of all necessary context."""
        user_id = state["user_id"]
        user_input = state["user_input"]
        character = state["character"]
        context_variables = state.get("context_variables", {})
        
        # Use extracted search terms if available from classifier (SPEC-E32)
        classification = state.get("classification", {})
        query_extraction = classification.get("query") if classification else None
        
        # Determine the best query for memory search
        if query_extraction and query_extraction.get("search_terms"):
            search_query = query_extraction["search_terms"]
            logger.debug(f"Using extracted search terms: {search_query}")
        else:
            search_query = user_input
        
        # Extract time range filter if present
        time_range = query_extraction.get("time_range") if query_extraction else None
        
        # Check if memories were pre-fetched (e.g., cross-bot pipeline)
        prefetched_memories = context_variables.get("prefetched_memories")
        
        # Prepare tasks for parallel execution
        tasks = {}
        
        # 1. Memories (if not prefetched)
        if prefetched_memories is not None:
            logger.debug(f"Using {len(prefetched_memories)} pre-fetched memories")
            memories = prefetched_memories
        else:
            # Use extracted search_query instead of raw user_input
            collection_name = f"whisperengine_memory_{character.name}" if character.name else None
            tasks["user_memories"] = memory_manager.search_memories(
                search_query, user_id, limit=5, collection_name=collection_name, time_range=time_range
            )
            tasks["broadcast_memories"] = memory_manager.search_memories(
                search_query, "__broadcast__", limit=2, collection_name=collection_name, time_range=time_range
            )

        # 2. Evolution (Trust, Mood, Feedback)
        tasks["evolution"] = self.context_builder.get_evolution_context(user_id, character.name)
        
        # 3. Goals
        tasks["goals"] = self.context_builder.get_goal_context(user_id, character.name)
        
        # 4. Diary
        if settings.ENABLE_CHARACTER_DIARY:
            tasks["diary"] = self.context_builder.get_diary_context(character.name)
            
        # 5. Dream
        if settings.ENABLE_DREAM_SEQUENCES and user_id:
            user_name = context_variables.get("user_name", "the user")
            # We need character context for dream generation. 
            # We can use the raw system prompt from character object.
            tasks["dream"] = self.context_builder.get_dream_context(
                user_id=user_id,
                user_name=user_name,
                char_name=character.name,
                character_context=character.system_prompt[:500] if character.system_prompt else ""
            )
            
        # 6. Knowledge Graph
        prefetched_knowledge = context_variables.get("prefetched_knowledge")
        if prefetched_knowledge:
            # If we have pre-fetched knowledge (string), wrap it in a future-like result or just use it
            # Since we are using asyncio.gather, we can't just assign the string to tasks["knowledge"] 
            # if we expect a coroutine.
            # However, we process results later.
            # Let's just set it directly in context_results if we skip the task.
            pass 
        else:
            tasks["knowledge"] = self.context_builder.get_knowledge_context(user_id, character.name, user_input)
        
        # 7. Known Bots
        guild_id = context_variables.get("guild_id")
        tasks["known_bots"] = self.context_builder.get_known_bots_context(character.name, guild_id)
        
        # 8. Stigmergy (Shared Artifacts)
        if settings.ENABLE_STIGMERGIC_DISCOVERY:
            tasks["stigmergy"] = self.context_builder.get_stigmergy_context(user_input, user_id, character.name)

        # Execute all tasks in parallel
        # We need to map keys back to results
        task_keys = list(tasks.keys())
        task_values = list(tasks.values())
        
        results = await asyncio.gather(*task_values, return_exceptions=True)
        
        # Process results
        context_results = {}
        
        # Add prefetched knowledge if available
        if prefetched_knowledge:
            context_results["knowledge"] = prefetched_knowledge

        user_memories = []
        broadcast_memories = []
        
        for i, key in enumerate(task_keys):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Context fetch failed for {key}: {result}")
                if key in ["user_memories", "broadcast_memories"]:
                    pass # memories will be empty
                else:
                    context_results[key] = "" # Default to empty string
            else:
                if key == "user_memories":
                    user_memories.extend(result)
                elif key == "broadcast_memories":
                    broadcast_memories.extend(result)
                else:
                    context_results[key] = result

        if prefetched_memories:
            user_memories = prefetched_memories

        context_results["user_memories"] = user_memories
        context_results["broadcast_memories"] = broadcast_memories
        
        # Combine for neighborhood search and backward compatibility
        memories = user_memories + broadcast_memories
        context_results["memories"] = memories
        
        # Phase 2.5.1: Unified Memory - Fetch Memory Neighborhood
        # If we have memories, fetch their graph connections (Vector-First Traversal)
        if memories:
            try:
                # Extract IDs (search_memories returns dicts)
                memory_ids = [m.get("id") for m in memories if m.get("id")]
                if memory_ids:
                    neighborhood = await knowledge_manager.get_memory_neighborhood(memory_ids)
                    if neighborhood:
                        context_results["unified_neighborhood"] = neighborhood
                        logger.debug(f"Retrieved {len(neighborhood)} Unified Memory connections for {len(memory_ids)} memories")
            except Exception as e:
                logger.warning(f"Failed to fetch Unified Memory neighborhood: {e}")
        
        return {
            "context": context_results
        }

    async def classifier_node(self, state: SuperGraphState):
        """Determines complexity and intent."""
        result = await self.classifier.classify(
            text=state["user_input"],
            chat_history=state["chat_history"],
            user_id=state["user_id"],
            bot_name=state["character"].name
        )
        return {"classification": result}

    async def prompt_builder_node(self, state: SuperGraphState):
        """Constructs the system prompt using gathered context."""
        character = state["character"]
        user_input = state["user_input"]
        user_id = state["user_id"]
        context_variables = state.get("context_variables", {})
        context_data = state.get("context", {})
        
        # Determine if tools will be available based on routing logic
        # This mirrors router_logic() to predict the path before building the prompt
        classification = state.get("classification")
        image_urls = state.get("image_urls")
        
        # Tools are NOT available in fast path - determine using same logic as router_logic
        tools_available = True
        if image_urls:
            # Image uploads -> Fast (Vision) -> no tools
            tools_available = False
        elif user_id == "proactive_trigger":
            # Proactive posts (internal monologue) should ALWAYS have full tool access
            # This allows the bot to decide to generate an image or search the web proactively
            tools_available = True
        elif not classification:
            # No classification -> fast -> no tools
            tools_available = False
        else:
            complexity = classification.get("complexity", "SIMPLE")
            intents = classification.get("intents", [])
            
            # Search intent with web search enabled -> reflective -> tools available
            if "search" in intents and settings.ENABLE_WEB_SEARCH:
                tools_available = True
            # Complex -> reflective -> tools available
            elif settings.ENABLE_REFLECTIVE_MODE and complexity in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                tools_available = True
            # Low complexity -> character agent -> has tools
            elif complexity == "COMPLEX_LOW":
                tools_available = True
            else:
                # Default (SIMPLE) -> character agent -> has tools
                # All queries now have single-tool-call capability for better personalization
                tools_available = True
        
        # 1. Build base system context (Identity, Trust, Goals, Knowledge, Diary, Dreams)
        # Pass the pre-fetched context to avoid re-fetching
        # Pass tools_available to control meta instruction content (e.g., "use image tool")
        system_content = await self.context_builder.build_system_context(
            character=character,
            user_message=user_input,
            user_id=user_id,
            context_variables=context_variables,
            prefetched_context=context_data,
            tools_available=tools_available
        )
        
        # 2. Inject Vector Memories (fetched in context_node)
        # SKIP memory injection if the user uploaded documents - this prevents context pollution
        # where the LLM confuses past conversation memories with the current document analysis request
        has_documents = context_variables.get("has_documents", False)
        
        # Retrieve separated memories
        user_memories = context_data.get("user_memories", [])
        broadcast_memories = context_data.get("broadcast_memories", [])
        
        # Fallback for backward compatibility
        if not user_memories and not broadcast_memories:
            user_memories = context_data.get("memories", [])
            
        all_memories = user_memories + broadcast_memories
        
        # Check for temporal query mismatch (SPEC-E32: anti-confabulation)
        # If user asked about a specific date but we have no memories from that date, warn the agent
        classification = state.get("classification", {})
        query_extraction = classification.get("query") if classification else None
        time_range = query_extraction.get("time_range") if query_extraction else None
        
        temporal_warning = ""
        if time_range:
            start_date = time_range.get("start", "")
            end_date = time_range.get("end", "")
            
            # Check if any memories fall within the requested range
            has_matching_memory = False
            for mem in all_memories:
                mem_ts = mem.get("timestamp", "")
                if mem_ts:
                    mem_date = mem_ts[:10]  # Extract YYYY-MM-DD
                    if start_date <= mem_date <= end_date:
                        has_matching_memory = True
                        break
            
            if not has_matching_memory and all_memories:
                # We have memories but none from the requested date
                temporal_warning = f"\n\n⚠️ TEMPORAL MISMATCH: The user is asking about {start_date} to {end_date}, but NONE of the memories below are from that date range. My database records may not go back that far.\n\nCRITICAL: You CANNOT \"remember\" specific details (topics, quotes, events, letter titles) from a date you have no records of. Do NOT list things that \"happened\" - you genuinely don't know. Simply tell the user: \"I don't have records from that date - my stored history starts from [earliest date you can see]. Would you like to tell me about it so I can remember it going forward?\"\n"
                logger.info(f"Temporal mismatch detected: requested {start_date} to {end_date}, no matching memories")
            elif not all_memories:
                # No memories at all
                temporal_warning = f"\n\n⚠️ TEMPORAL QUERY: The user is asking about {start_date} to {end_date}, but I found NO memories from that time period. My database records may not go back that far.\n\nCRITICAL: You CANNOT \"remember\" specific details from a date you have no records of. Do NOT make up topics, quotes, or events. Simply tell the user: \"I don't have records from that date. Would you like to share what we discussed so I can remember it?\"\n"
                logger.info(f"Temporal query with no results: requested {start_date} to {end_date}")

        if (user_memories or broadcast_memories) and not has_documents:
            
            def format_memory_list(mems):
                formatted = ""
                for mem in mems:
                    # Format: [Author]: Content (Time) - timestamp at END to avoid LLM echoing it as content
                    rel_time = mem.get("relative_time", "unknown time")
                    content = mem.get("content", "")
                    # Truncate very long memories to avoid bloating context
                    if len(content) > 500:
                        content = content[:500] + "..."
                    
                    # ADR-014: Show author for multi-party attribution
                    author_name = mem.get("author_name")
                    author_is_bot = mem.get("author_is_bot", False)
                    
                    if author_name:
                        bot_tag = " (bot)" if author_is_bot else ""
                        formatted += f"- [{author_name}{bot_tag}]: {content} ({rel_time})\n"
                    else:
                        # Legacy memories without author - use role as hint
                        role = mem.get("role", "unknown")
                        user_name = mem.get("user_name")
                        
                        if role == "human":
                            # Fallback to user_name if available, otherwise "User"
                            name_label = user_name if user_name else "User"
                            formatted += f"- [{name_label}]: {content} ({rel_time})\n"
                        elif role == "ai":
                            formatted += f"- [You]: {content} ({rel_time})\n"
                        else:
                            formatted += f"- {content} ({rel_time})\n"
                return formatted

            user_memory_context = format_memory_list(user_memories)
            broadcast_memory_context = format_memory_list(broadcast_memories)
            
            if user_memory_context:
                system_content += f"\n\n[RELEVANT MEMORY & KNOWLEDGE]\n{user_memory_context}\n"
            
            if broadcast_memory_context:
                system_content += f"\n\n[SHARED/PUBLIC CONTEXT (GOSSIP/NEWS)]\n(These are public events or things you heard, NOT direct conversations with the current user)\n{broadcast_memory_context}\n"
                
            # Phase 2.5.1: Inject Unified Memory Context (Graph Connections)
            neighborhood = context_data.get("unified_neighborhood", [])
            if neighborhood:
                unified_text = ""
                seen_associations = set()
                
                for item in neighborhood:
                    # Format: Entity (Predicate)
                    assoc = f"{item['entity']} ({item['predicate']})"
                    if assoc not in seen_associations:
                        unified_text += f"- Associated with: {assoc}\n"
                        seen_associations.add(assoc)
                
                if unified_text:
                    system_content += f"\n[ASSOCIATIVE CONNECTIONS]\n(These concepts are structurally linked to the memories above)\n{unified_text}\n"

            system_content += "(Use this information naturally. Do not explicitly state 'I see in my memory' or 'According to the database'. Treat this as your own knowledge.)\n"
        elif has_documents:
            logger.debug("Skipping memory context injection for document-focused request")
        
        # Add temporal warning if applicable (anti-confabulation)
        if temporal_warning:
            system_content += temporal_warning

        # 3. Template Variable Substitution
        # Replace {user_name}, {current_datetime}, and any other context variables
        if context_variables:
            for key, value in context_variables.items():
                if isinstance(value, str):
                    system_content = system_content.replace(f"{{{key}}}", value)
        
        # Fallback: If {current_datetime} is still present, replace it
        if "{current_datetime}" in system_content:
            now_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M")
            system_content = system_content.replace("{current_datetime}", now_str)

        # 4. Final Identity Anchor (Anti-Identity-Bleed)
        # MUST be the absolute last thing in the prompt to override any memory context
        if context_variables.get("user_name"):
            system_content += self.context_builder.get_identity_anchor(context_variables["user_name"])

        return {"system_prompt": system_content} 

    def router_logic(self, state: SuperGraphState) -> Literal["reflective", "character", "fast"]:
        """Decides which agent to use based on complexity."""
        classification = state.get("classification")
        if not classification:
            return "fast"
            
        complexity = classification["complexity"]
        intents = classification.get("intents", [])
        image_urls = state.get("image_urls")
        
        # Image uploads -> Fast (Vision)
        if image_urls:
            return "fast"
        
        # Search intent -> Always use Reflective (has web_search tool)
        if "search" in intents and settings.ENABLE_WEB_SEARCH:
            return "reflective"
            
        # Complex -> Reflective
        if settings.ENABLE_REFLECTIVE_MODE and complexity in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            return "reflective"
            
        # Low Complexity + Agency -> Character Agent
        if complexity == "COMPLEX_LOW":
            return "character"
            
        # Default (SIMPLE) -> Character Agent (ensures all queries have tool access)
        # This allows even simple queries to use mem_search for better personalization
        return "character"

    async def reflective_subgraph_node(self, state: SuperGraphState):
        """Wraps the ReflectiveGraphAgent."""
        classification = state.get("classification")
        intents = classification["intents"] if classification else []
        callback = state.get("callback")
        context_variables = state.get("context_variables", {})
        
        response, _ = await self.reflective_agent.run(
            user_input=state["user_input"],
            user_id=state["user_id"],
            system_prompt=state["system_prompt"] or "", 
            chat_history=state["chat_history"],
            image_urls=state["image_urls"],
            detected_intents=intents,
            callback=callback,
            guild_id=context_variables.get("guild_id"),
            channel=context_variables.get("channel"),
            character_name=state["character"].name
        )
        return {"final_response": response}

    async def character_subgraph_node(self, state: SuperGraphState):
        """Wraps the CharacterGraphAgent."""
        callback = state.get("callback")
        context_variables = state.get("context_variables", {})
        
        response = await self.character_agent.run(
            user_input=state["user_input"],
            user_id=state["user_id"],
            system_prompt=state["system_prompt"] or "",
            chat_history=state["chat_history"],
            character_name=state["character"].name,
            image_urls=state["image_urls"],
            callback=callback,
            guild_id=context_variables.get("guild_id"),
            channel=context_variables.get("channel")
        )
        return {"final_response": response}

    async def fast_responder_node(self, state: SuperGraphState):
        """Simple LLM call for fast responses."""
        system_prompt = state.get("system_prompt", "")
        chat_history = state.get("chat_history", [])
        user_input = state.get("user_input", "")
        image_urls = state.get("image_urls")

        # Construct messages
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(chat_history)
        
        if image_urls and settings.LLM_SUPPORTS_VISION:
            # Handle images - convert to base64 if URL requires it (Discord CDN) or provider requires it
            content: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
            
            async with httpx.AsyncClient() as client:
                for img_url in image_urls:
                    if should_use_base64(img_url, settings.LLM_PROVIDER):
                        # Download and encode as base64 (needed for Discord CDN URLs)
                        try:
                            img_response = await client.get(img_url, timeout=10.0)
                            img_response.raise_for_status()
                            # Process image (handles animated GIFs by extracting first frame)
                            mime_type = img_response.headers.get("content-type", "image/png")
                            img_b64, mime_type = process_image_for_llm(img_response.content, mime_type)
                            content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                            })
                        except Exception as e:
                            logger.error(f"Failed to download/encode image {img_url}: {e}")
                            # Don't fallback to raw Discord CDN URL - it won't work for external LLMs
                            # Instead, add a text note so the LLM knows an image was present
                            content.append({"type": "text", "text": "[An image was shared but could not be processed]"})
                    else:
                        # Provider accepts direct URLs and URL doesn't require base64
                        content.append({"type": "image_url", "image_url": {"url": img_url}})
            messages.append(HumanMessage(content=content))
        elif image_urls:
            # Vision not supported, just add text
            messages.append(HumanMessage(content=user_input))
        else:
            messages.append(HumanMessage(content=user_input))

        try:
            # LLM call with retry for transient errors (500s, rate limits, etc.)
            response = await invoke_with_retry(self.fast_llm.ainvoke, messages, max_retries=3)
            return {"final_response": response.content}
        except Exception as e:
            logger.error(f"Fast responder failed: {e}")
            # Check for image-specific errors (animated GIF, format issues, etc.)
            image_error = get_image_error_message(e)
            if image_error:
                return {"final_response": image_error}
            return {"final_response": "I'm having a bit of trouble thinking clearly right now."}

    @traceable(name="MasterGraphAgent.run", run_type="chain")
    async def run(self, **kwargs):
        """Entry point for the Supergraph."""
        start_time = datetime.datetime.now()
        logger.info("Executing MasterGraphAgent.run")
        # Explicitly cast to dict to satisfy type checker, though TypedDict is a dict at runtime
        input_state = cast(SuperGraphState, kwargs)
        result = await self.graph.ainvoke(input_state, config={"run_name": "MasterGraphExecution"})
        
        # Log metrics
        latency = (datetime.datetime.now() - start_time).total_seconds()
        
        # Determine mode for metrics (map 'character' to 'agency' for dashboard compatibility)
        routing_mode = self.router_logic(result)
        metric_mode = "agency" if routing_mode == "character" else routing_mode
        
        complexity = result.get("classification", {}).get("complexity", "SIMPLE")
        
        asyncio.create_task(self._log_metrics(
            user_id=input_state.get("user_id"),
            character_name=input_state.get("character").name,
            latency=latency,
            mode=metric_mode,
            complexity=complexity
        ))
        
        return result["final_response"]

    async def run_stream(self, **kwargs):
        """
        Streaming entry point for the Supergraph.
        Yields the final response as a single chunk after processing.
        Callbacks are handled internally by the subgraphs for status updates.
        """
        start_time = datetime.datetime.now()
        logger.info("Executing MasterGraphAgent.run_stream")
        input_state = cast(SuperGraphState, kwargs)
        result = await self.graph.ainvoke(input_state, config={"run_name": "MasterGraphExecution"})
        
        # Log metrics
        latency = (datetime.datetime.now() - start_time).total_seconds()
        
        # Determine mode for metrics (map 'character' to 'agency' for dashboard compatibility)
        routing_mode = self.router_logic(result)
        metric_mode = "agency" if routing_mode == "character" else routing_mode
        
        complexity = result.get("classification", {}).get("complexity", "SIMPLE")
        
        asyncio.create_task(self._log_metrics(
            user_id=input_state.get("user_id"),
            character_name=input_state.get("character").name,
            latency=latency,
            mode=metric_mode,
            complexity=complexity
        ))
        
        response = result.get("final_response", "")
        if response:
            yield response

# Singleton
master_graph_agent = MasterGraphAgent()
