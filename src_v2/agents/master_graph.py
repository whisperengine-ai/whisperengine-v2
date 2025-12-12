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
        
        # Build Graph
        workflow = StateGraph(SuperGraphState)
        
        # Add Nodes
        workflow.add_node("context_fetcher", self.context_node)
        workflow.add_node("classifier", self.classifier_node)
        workflow.add_node("prompt_builder", self.prompt_builder_node)
        workflow.add_node("reflective_agent", self.reflective_subgraph_node)
        workflow.add_node("character_agent", self.character_subgraph_node)
        workflow.add_node("fast_responder", self.fast_responder_node) # Fallback/Simple
        
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
        
        workflow.add_edge("reflective_agent", END)
        workflow.add_edge("character_agent", END)
        workflow.add_edge("fast_responder", END)
        
        self.graph = workflow.compile()

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

        memories = []
        
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
                    memories.extend(result)
                elif key == "broadcast_memories":
                    memories.extend(result)
                else:
                    context_results[key] = result

        if prefetched_memories:
            memories = prefetched_memories

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
        
        # 1. Build base system context (Identity, Trust, Goals, Knowledge, Diary, Dreams)
        # Pass the pre-fetched context to avoid re-fetching
        system_content = await self.context_builder.build_system_context(
            character=character,
            user_message=user_input,
            user_id=user_id,
            context_variables=context_variables,
            prefetched_context=context_data
        )
        
        # 2. Inject Vector Memories (fetched in context_node)
        # SKIP memory injection if the user uploaded documents - this prevents context pollution
        # where the LLM confuses past conversation memories with the current document analysis request
        has_documents = context_variables.get("has_documents", False)
        memories = context_data.get("memories", [])
        
        if memories and not has_documents:
            memory_context = ""
            for mem in memories:
                # Format: Content (Time) - timestamp at END to avoid LLM echoing it as content
                rel_time = mem.get("relative_time", "unknown time")
                content = mem.get("content", "")
                # Truncate very long memories to avoid bloating context
                if len(content) > 500:
                    content = content[:500] + "..."
                memory_context += f"- {content} ({rel_time})\n"
            
            if memory_context:
                system_content += f"\n\n[RELEVANT MEMORY & KNOWLEDGE]\n{memory_context}\n"
                
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
            
        # Default -> Fast
        return "fast"

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
        logger.info("Executing MasterGraphAgent.run")
        # Explicitly cast to dict to satisfy type checker, though TypedDict is a dict at runtime
        input_state = cast(SuperGraphState, kwargs)
        result = await self.graph.ainvoke(input_state, config={"run_name": "MasterGraphExecution"})
        return result["final_response"]

    async def run_stream(self, **kwargs):
        """
        Streaming entry point for the Supergraph.
        Yields the final response as a single chunk after processing.
        Callbacks are handled internally by the subgraphs for status updates.
        """
        logger.info("Executing MasterGraphAgent.run_stream")
        input_state = cast(SuperGraphState, kwargs)
        result = await self.graph.ainvoke(input_state, config={"run_name": "MasterGraphExecution"})
        response = result.get("final_response", "")
        if response:
            yield response

# Singleton
master_graph_agent = MasterGraphAgent()
