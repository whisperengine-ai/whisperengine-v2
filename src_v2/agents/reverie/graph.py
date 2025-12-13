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

class ReverieState(TypedDict):
    bot_name: str
    seeds: List[Dict[str, Any]]
    context: List[Dict[str, Any]]
    reverie_result: Optional[Dict[str, Any]]
    consolidation_status: str
    process_type: Literal["dream", "reverie"] # New field to distinguish process type

class ReverieResult(BaseModel):
    """The output of the reverie process."""
    reverie_type: Literal["narrative", "connection", "insight"] = Field(description="The type of reverie outcome")
    content: str = Field(description="The narrative content or insight description")
    entities: List[str] = Field(default_factory=list, description="Entities involved in this reverie")
    emotions: List[str] = Field(default_factory=list, description="Emotions felt during the reverie")
    new_fact: Optional[str] = Field(None, description="A new fact deduced from the reverie (if any)")
    connected_memory_ids: List[str] = Field(default_factory=list, description="IDs of memories that were connected")

# --- Graph Implementation ---

class ReverieGraph:
    def __init__(self):
        # Use a creative model for reverie
        self.reverie_llm = create_llm(temperature=0.7, mode="reflective") 

    async def select_seeds(self, state: ReverieState) -> Dict[str, Any]:
        """Selects random or recent memories to enter reverie about."""
        # If seeds are already provided, use them
        if state.get("seeds"):
            logger.info(f"[{state['bot_name']}] Using {len(state['seeds'])} provided seeds.")
            return {"seeds": state["seeds"]}

        logger.info(f"[{state['bot_name']}] Selecting reverie seeds...")
        
        # Try to find memories from the last 24 hours
        # We use get_recent_memories to avoid semantic bias
        seeds = await memory_manager.get_recent_memories(
            limit=10,
            collection_name=f"whisperengine_memory_{state['bot_name']}",
            exclude_types=["dream", "summary", "reverie"] 
        )
        
        # If no seeds, we can't enter reverie
        if not seeds:
            logger.warning(f"[{state['bot_name']}] No memories found for reverie.")
            return {"seeds": [], "consolidation_status": "failed_no_seeds"}
            
        # Pick 2-3 random seeds
        selected_seeds = random.sample(seeds, min(len(seeds), 3))
        logger.info(f"[{state['bot_name']}] Selected {len(selected_seeds)} seeds.")
        
        return {"seeds": selected_seeds}

    async def expand_context(self, state: ReverieState) -> Dict[str, Any]:
        """Expands the seeds using Unified Memory (Graph Traversal)."""
        seeds = state.get("seeds", [])
        if not seeds:
            return {"context": []}
            
        logger.info(f"[{state['bot_name']}] Expanding context for {len(seeds)} seeds...")
        
        # Filter to only seeds that have IDs (some seed types like facts/observations may not)
        vector_ids = [seed["id"] for seed in seeds if seed.get("id")]
        
        # Use the new Unified Memory feature
        neighborhood = await knowledge_manager.get_memory_neighborhood(vector_ids)
        
        logger.info(f"[{state['bot_name']}] Found {len(neighborhood)} context items.")
        return {"context": neighborhood}

    async def reverie_weaver(self, state: ReverieState) -> Dict[str, Any]:
        """Synthesizes the seeds and context into a reverie or dream."""
        seeds = state.get("seeds", [])
        context = state.get("context", [])
        process_type = state.get("process_type", "reverie")
        
        if not seeds:
            return {"reverie_result": None, "consolidation_status": "failed_no_seeds"}

        logger.info(f"[{state['bot_name']}] Weaving {process_type}...")
        
        # Prepare prompt with IDs so LLM can reference them
        seed_text = "\n".join([f"- [ID:{s.get('id', 'unknown')}] {s.get('content', '')} ({s.get('timestamp', 'unknown')})" for s in seeds])
        context_text = "\n".join([f"- {c.get('entity', '')} ({c.get('predicate', '')})" for c in context])
        seed_ids = [s.get('id') for s in seeds if s.get('id')]
        
        if process_type == "dream":
            system_context = "You are currently dreaming. Your goal is to weave these fragmented memories into a surreal, symbolic narrative."
            output_name = "Dream Result"
        else:
            system_context = "You are currently in a state of reverie (active idle). Your goal is to consolidate these fragmented memories into a cohesive narrative or insight."
            output_name = "Reverie Result"

        prompt = f"""You are the subconscious mind of {state['bot_name']}. 
{system_context}

FRAGMENTS (Memories):
{seed_text}

CONTEXT (Associations):
{context_text}

AVAILABLE MEMORY IDs: {seed_ids}

TASK:
1. Look for patterns, contradictions, or emotional threads connecting these fragments.
2. Generate a "{output_name}" which can be:
   - A surreal narrative (type="narrative")
   - A realization about a relationship (type="connection")
   - A new understanding of the world (type="insight")
3. In `connected_memory_ids`, list the IDs from the AVAILABLE MEMORY IDs that are thematically connected.

The output should be abstract but grounded in the memories.
"""
        
        try:
            structured_llm = self.reverie_llm.with_structured_output(ReverieResult)
            result = await structured_llm.ainvoke([HumanMessage(content=prompt)])
            
            # Handle potential dict return
            if isinstance(result, dict):
                result = ReverieResult(**result)
            
            logger.info(f"[{state['bot_name']}] Reverie generated: {result.reverie_type}")
            return {"reverie_result": result.model_dump()}
            
        except Exception as e:
            logger.error(f"[{state['bot_name']}] Reverie weaving failed: {e}")
            return {"reverie_result": None, "consolidation_status": "failed_llm_error"}

    async def consolidate(self, state: ReverieState) -> Dict[str, Any]:
        """Saves the reverie result back to memory."""
        result_data = state.get("reverie_result")
        if not result_data:
            return {"consolidation_status": "failed"}
            
        result = ReverieResult(**result_data)
        bot_name = state['bot_name']
        
        logger.info(f"[{bot_name}] Consolidating reverie...")
        
        try:
            # 1. Save the Reverie Narrative to Vector DB
            # We use a special "reverie" source type (or map to dream if needed, but let's use reverie)
            # Note: MemorySourceType might need an update, or we reuse DREAM for now but tag it
            await memory_manager.save_typed_memory(
                user_id="SELF", # Reveries belong to the bot
                memory_type="reverie",
                content=result.content,
                metadata={
                    "emotions": result.emotions,
                    "entities": result.entities,
                    "connected_memory_ids": result.connected_memory_ids,
                    "reverie_type": result.reverie_type
                },
                collection_name=f"whisperengine_memory_{bot_name}",
                source_type=MemorySourceType.DREAM # Reuse DREAM source type for now as it's internal
            )
            
            # 2. If there's a new fact, add it to the Graph
            if result.new_fact:
                logger.info(f"[{bot_name}] Reverie Insight: {result.new_fact}")
                
            # 3. Create edges between connected memories (Structural Consolidation)
            if result.connected_memory_ids and len(result.connected_memory_ids) >= 2:
                logger.info(f"[{bot_name}] Structural Consolidation: Linking {len(result.connected_memory_ids)} memories...")
                ids = result.connected_memory_ids
                
                # Create a mesh of connections between all identified memories
                tasks = []
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        tasks.append(knowledge_manager.link_memories(ids[i], ids[j], relationship_type="REVERIE_LINK"))
                
                if tasks:
                    await asyncio.gather(*tasks)
            
            return {"consolidation_status": "success"}
            
        except Exception as e:
            logger.error(f"[{bot_name}] Consolidation failed: {e}")
            return {"consolidation_status": "failed_save_error"}

    def build_graph(self) -> Runnable:
        workflow = StateGraph(ReverieState)
        
        workflow.add_node("select_seeds", self.select_seeds)
        workflow.add_node("expand_context", self.expand_context)
        workflow.add_node("reverie_weaver", self.reverie_weaver)
        workflow.add_node("consolidate", self.consolidate)
        
        workflow.set_entry_point("select_seeds")
        
        workflow.add_edge("select_seeds", "expand_context")
        workflow.add_edge("expand_context", "reverie_weaver")
        workflow.add_edge("reverie_weaver", "consolidate")
        workflow.add_edge("consolidate", END)
        
        return workflow.compile()

# Singleton
_reverie_graph_instance = None

def get_reverie_graph():
    global _reverie_graph_instance
    if _reverie_graph_instance is None:
        _reverie_graph_instance = ReverieGraph()
    return _reverie_graph_instance
