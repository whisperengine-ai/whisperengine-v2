from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.trust import trust_manager


class ContextBuilder:
    """
    Orchestrates the retrieval of context from multiple sources:
    1. Postgres (Recent Chat History) - "What just happened"
    2. Qdrant (Vector Memory) - "What is relevant from the past"
    3. Neo4j (Knowledge Graph) - "What facts do we know"
    4. Trust System - "How close are we"
    """
    
    def __init__(self):
        pass

    async def build_context(
        self, 
        user_id: str, 
        character_name: str, 
        query: str, 
        limit_history: int = 10,
        limit_memories: int = 5,
        limit_summaries: int = 3
    ) -> Dict[str, Any]:
        """
        Fetches all context in parallel.
        """
        
        # Define tasks
        tasks = {
            "history": memory_manager.get_recent_history(user_id, character_name, limit=limit_history),
            "memories": memory_manager.search_memories(query, user_id, limit=limit_memories),
            "summaries": memory_manager.search_summaries(query, user_id, limit=limit_summaries),
            "knowledge": knowledge_manager.query_graph(user_id, query, bot_name=character_name),
            "trust": trust_manager.get_relationship_level(user_id, character_name)
        }
        
        # Execute in parallel
        # We use return_exceptions=True to prevent one failure from crashing the whole request
        results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Process results
        context = {}
        keys = list(tasks.keys())
        
        for i, result in enumerate(results_list):
            key = keys[i]
            if isinstance(result, Exception):
                logger.error(f"ContextBuilder failed to fetch {key}: {result}")
                # Provide safe defaults
                if key in ["history", "memories", "summaries"]:
                    context[key] = []
                elif key == "trust":
                    context[key] = {"trust_score": 0, "level": 1, "level_label": "Stranger"}
                else:
                    context[key] = ""
            else:
                context[key] = result
                
        return context


# Global instance
context_builder = ContextBuilder()
