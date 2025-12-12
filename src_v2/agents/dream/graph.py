import asyncio
import json
import random
from typing import List, Dict, Any, TypedDict, Optional, Literal
from loguru import logger
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import Runnable

from src_v2.agents.llm_factory import create_llm
from src_v2.memory.manager import memory_manager
from src_v2.memory.models import MemorySourceType
from src_v2.knowledge.manager import knowledge_manager
from src_v2.config.settings import settings

# --- State Definition ---

class DreamState(TypedDict):
    bot_name: str
    seeds: List[Dict[str, Any]]
    context: List[Dict[str, Any]]
    dream_result: Optional[Dict[str, Any]]
    consolidation_status: str

class DreamResult(BaseModel):
    """The output of the dreaming process."""
    dream_type: Literal["narrative", "connection", "insight"] = Field(description="The type of dream outcome")
    content: str = Field(description="The narrative content or insight description")
    entities: List[str] = Field(default_factory=list, description="Entities involved in this dream")
    emotions: List[str] = Field(default_factory=list, description="Emotions felt during the dream")
    new_fact: Optional[str] = Field(None, description="A new fact deduced from the dream (if any)")
    connected_memory_ids: List[str] = Field(default_factory=list, description="IDs of memories that were connected")

# --- Graph Implementation ---

class DreamGraph:
    def __init__(self):
        # Use a creative model for dreaming
        self.dreamer_llm = create_llm(temperature=0.7, mode="reflective") 

    async def select_seeds(self, state: DreamState) -> Dict[str, Any]:
        """Selects random or recent memories to dream about."""
        # If seeds are already provided (e.g. from DreamManager), use them
        if state.get("seeds"):
            logger.info(f"[{state['bot_name']}] Using {len(state['seeds'])} provided seeds.")
            return {"seeds": state["seeds"]}

        logger.info(f"[{state['bot_name']}] Selecting dream seeds...")
        
        # TODO: Implement get_unconsolidated_memories in MemoryManager
        # For now, we'll just search for recent memories as a proxy
        # or pick random ones if we can't find specific "unconsolidated" ones.
        
        # Try to find memories from the last 24 hours
        # We use get_recent_memories to avoid semantic bias
        seeds = await memory_manager.get_recent_memories(
            limit=10,
            collection_name=f"whisperengine_memory_{state['bot_name']}",
            exclude_types=["dream", "summary"] # Don't dream about dreams (yet)
        )
        
        # If no seeds, we can't dream
        if not seeds:
            logger.warning(f"[{state['bot_name']}] No memories found to dream about.")
            return {"seeds": [], "consolidation_status": "failed_no_seeds"}
            
        # Pick 2-3 random seeds
        selected_seeds = random.sample(seeds, min(len(seeds), 3))
        logger.info(f"[{state['bot_name']}] Selected {len(selected_seeds)} seeds.")
        
        return {"seeds": selected_seeds}

    async def expand_context(self, state: DreamState) -> Dict[str, Any]:
        """Expands the seeds using the Synapse (Graph Traversal)."""
        seeds = state.get("seeds", [])
        if not seeds:
            return {"context": []}
            
        logger.info(f"[{state['bot_name']}] Expanding context for {len(seeds)} seeds...")
        
        vector_ids = [seed["id"] for seed in seeds]
        
        # Use the new Synapse feature
        neighborhood = await knowledge_manager.get_memory_neighborhood(vector_ids)
        
        logger.info(f"[{state['bot_name']}] Found {len(neighborhood)} context items.")
        return {"context": neighborhood}

    async def dream_weaver(self, state: DreamState) -> Dict[str, Any]:
        """Synthesizes the seeds and context into a dream."""
        seeds = state.get("seeds", [])
        context = state.get("context", [])
        
        if not seeds:
            return {"dream_result": None, "consolidation_status": "failed_no_seeds"}

        logger.info(f"[{state['bot_name']}] Weaving dream...")
        
        # Prepare prompt with IDs so LLM can reference them
        seed_text = "\n".join([f"- [ID:{s.get('id', 'unknown')}] {s.get('content', '')} ({s.get('timestamp', 'unknown')})" for s in seeds])
        context_text = "\n".join([f"- {c.get('entity', '')} ({c.get('predicate', '')})" for c in context])
        seed_ids = [s.get('id') for s in seeds if s.get('id')]
        
        prompt = f"""You are the subconscious mind of {state['bot_name']}. 
You are currently dreaming. Your goal is to consolidate these fragmented memories into a cohesive narrative or insight.

FRAGMENTS (Memories):
{seed_text}

CONTEXT (Associations):
{context_text}

AVAILABLE MEMORY IDs: {seed_ids}

TASK:
1. Look for patterns, contradictions, or emotional threads connecting these fragments.
2. Generate a "Dream Result" which can be:
   - A surreal narrative (type="narrative")
   - A realization about a relationship (type="connection")
   - A new understanding of the world (type="insight")
3. In `connected_memory_ids`, list the IDs from the AVAILABLE MEMORY IDs that are thematically connected.

The dream should be abstract but grounded in the memories.
"""
        
        try:
            structured_llm = self.dreamer_llm.with_structured_output(DreamResult)
            result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
            
            # Handle potential dict return (though with_structured_output usually returns model)
            if isinstance(result, dict):
                result = DreamResult(**result)
            
            logger.info(f"[{state['bot_name']}] Dream generated: {result.dream_type}")
            return {"dream_result": result.model_dump()}
            
        except Exception as e:
            logger.error(f"[{state['bot_name']}] Dream weaving failed: {e}")
            return {"dream_result": None, "consolidation_status": "failed_llm_error"}

    async def consolidate(self, state: DreamState) -> Dict[str, Any]:
        """Saves the dream result back to memory."""
        result_data = state.get("dream_result")
        if not result_data:
            return {"consolidation_status": "failed"}
            
        result = DreamResult(**result_data)
        bot_name = state['bot_name']
        
        logger.info(f"[{bot_name}] Consolidating dream...")
        
        try:
            # 1. Save the Dream Narrative to Vector DB
            # We use a special "dream" source type
            await memory_manager.save_typed_memory(
                user_id="SELF", # Dreams belong to the bot
                memory_type="dream",
                content=result.content,
                metadata={
                    "emotions": result.emotions,
                    "entities": result.entities,
                    "connected_memory_ids": result.connected_memory_ids,
                    "dream_type": result.dream_type
                },
                collection_name=f"whisperengine_memory_{bot_name}",
                source_type=MemorySourceType.DREAM
            )
            
            # 2. If there's a new fact, add it to the Graph
            if result.new_fact:
                # We need a way to add facts without a user_id context sometimes, 
                # or we attribute it to the bot's self-model.
                # For now, we'll skip this or log it.
                logger.info(f"[{bot_name}] Dream Insight: {result.new_fact}")
                
            # 3. Create edges between connected memories (Structural Consolidation)
            if result.connected_memory_ids and len(result.connected_memory_ids) >= 2:
                logger.info(f"[{bot_name}] Structural Consolidation: Linking {len(result.connected_memory_ids)} memories...")
                ids = result.connected_memory_ids
                
                # Create a mesh of connections between all identified memories
                # Use asyncio.gather for parallel execution
                tasks = []
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        tasks.append(knowledge_manager.link_memories(ids[i], ids[j], relationship_type="DREAM_ASSOCIATION"))
                
                if tasks:
                    await asyncio.gather(*tasks)
            
            return {"consolidation_status": "success"}
            
        except Exception as e:
            logger.error(f"[{bot_name}] Consolidation failed: {e}")
            return {"consolidation_status": "failed_save_error"}

    def build_graph(self) -> Runnable:
        workflow = StateGraph(DreamState)
        
        workflow.add_node("select_seeds", self.select_seeds)
        workflow.add_node("expand_context", self.expand_context)
        workflow.add_node("dream_weaver", self.dream_weaver)
        workflow.add_node("consolidate", self.consolidate)
        
        workflow.set_entry_point("select_seeds")
        
        workflow.add_edge("select_seeds", "expand_context")
        workflow.add_edge("expand_context", "dream_weaver")
        workflow.add_edge("dream_weaver", "consolidate")
        workflow.add_edge("consolidate", END)
        
        return workflow.compile()

# Singleton
_dream_graph_instance = None

def get_dream_graph():
    global _dream_graph_instance
    if _dream_graph_instance is None:
        _dream_graph_instance = DreamGraph()
    return _dream_graph_instance
