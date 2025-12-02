import asyncio
import operator
import datetime
from typing import List, Optional, Dict, Any, TypedDict, Literal, cast, Callable, Awaitable
from loguru import logger
from langsmith import traceable
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from src_v2.config.settings import settings
from src_v2.core.character import Character
from src_v2.agents.llm_factory import create_llm
from src_v2.agents.classifier import ComplexityClassifier
from src_v2.agents.reflective_graph import ReflectiveGraphAgent
from src_v2.agents.character_graph import CharacterGraphAgent
from src_v2.agents.context_builder import ContextBuilder

# Managers for Context Node
from src_v2.memory.manager import memory_manager

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
    context: Optional[Dict[str, Any]] # {memories, facts, trust, goals}
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
        
        # Edges
        workflow.set_entry_point("context_fetcher")
        workflow.add_edge("context_fetcher", "classifier")
        workflow.add_edge("classifier", "prompt_builder")
        
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
        
        # Parallel gather
        # Note: ContextBuilder handles Trust, Goals, and Knowledge internally.
        # We only fetch Vector Memories here as they are query-specific and not handled by ContextBuilder.
        memories = await memory_manager.search_memories(user_input, user_id, limit=5)
        
        return {
            "context": {
                "memories": memories,
                "facts": [], # Handled by ContextBuilder
                "trust": None, # Handled by ContextBuilder
                "goals": [] # Handled by ContextBuilder
            }
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
        
        # 1. Build base system context (Identity, Trust, Goals, Knowledge, Diary, Dreams)
        system_content = await self.context_builder.build_system_context(
            character=character,
            user_message=user_input,
            user_id=user_id,
            context_variables=context_variables
        )
        
        # 2. Inject Vector Memories (fetched in context_node)
        memories = state.get("context", {}).get("memories", [])
        if memories:
            memory_context = ""
            for mem in memories:
                # Format: [Time] Content (Score)
                rel_time = mem.get("relative_time", "unknown time")
                content = mem.get("content", "")
                memory_context += f"- [{rel_time}] {content}\n"
            
            if memory_context:
                system_content += f"\n\n[RELEVANT MEMORY & KNOWLEDGE]\n{memory_context}\n"
                system_content += "(Use this information naturally. Do not explicitly state 'I see in my memory' or 'According to the database'. Treat this as your own knowledge.)\n"

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
        # intents = classification["intents"] # Unused for now
        image_urls = state.get("image_urls")
        
        # Image uploads -> Fast (Vision)
        if image_urls:
            return "fast"
            
        # Complex -> Reflective
        if settings.ENABLE_REFLECTIVE_MODE and complexity in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            return "reflective"
            
        # Low Complexity + Agency -> Character Agent
        if settings.ENABLE_CHARACTER_AGENCY and complexity == "COMPLEX_LOW":
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
            channel=context_variables.get("channel")
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
        
        if image_urls:
             # Handle images if present (though usually handled by CharacterAgent, fast path might get them if complexity is low)
             content = [{"type": "text", "text": user_input}]
             for url in image_urls:
                 content.append({"type": "image_url", "image_url": {"url": url}})
             messages.append(HumanMessage(content=content))
        else:
            messages.append(HumanMessage(content=user_input))

        try:
            response = await self.fast_llm.ainvoke(messages)
            return {"final_response": response.content}
        except Exception as e:
            logger.error(f"Fast responder failed: {e}")
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
