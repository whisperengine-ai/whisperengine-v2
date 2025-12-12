from typing import Type, Optional, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

class AnalyzeTopicInput(BaseModel):
    topic: str = Field(description="The topic, concept, or person to analyze deeply.")

class AnalyzeTopicTool(BaseTool):
    name: str = "analyze_topic"
    description: str = "Comprehensive research tool. Searches summaries, episodes, and facts simultaneously for a given topic. Use this for broad questions to get a complete picture."
    args_schema: Type[BaseModel] = AnalyzeTopicInput
    
    user_id: str = Field(exclude=True)
    bot_name: str = Field(exclude=True)

    def _run(self, topic: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, topic: str) -> str:
        from src_v2.memory.context_builder import context_builder
        
        # Fetch context using the new builder
        context = await context_builder.build_context(
            user_id=self.user_id,
            character_name=self.bot_name,
            query=topic,
            limit_memories=5,
            limit_summaries=3
        )
        
        # Format Summaries
        summaries_list = context.get("summaries", [])
        if summaries_list:
            summaries_formatted = "\n".join([
                f"- [Score: {r.get('meaningfulness', '?')}/5] {r.get('content', '')} ({r.get('timestamp', '')[:10]})" 
                for r in summaries_list
            ])
            summaries_str = f"Found {len(summaries_list)} Summaries:\n{summaries_formatted}"
        else:
            summaries_str = "No relevant summaries found."

        # Format Episodes
        episodes_list = context.get("memories", [])
        if episodes_list:
            episodes_formatted = "\n".join([f"- {r.get('content', '')}" for r in episodes_list])
            episodes_str = f"Found {len(episodes_list)} Episodes:\n{episodes_formatted}"
        else:
            episodes_str = "No specific memories found."

        # Format Facts
        facts_str = f"Graph Query Result: {context.get('knowledge', 'No facts found.')}"
        
        # Format Neighborhood (Enriched Graph)
        neighborhood = context.get("neighborhood", [])
        neighborhood_str = "No enriched connections found."
        if neighborhood:
            lines = []
            seen = set()
            for item in neighborhood:
                # Handle both Entity/Predicate and Memory/LinkType formats
                if "entity" in item and "predicate" in item:
                    # Check if it's a memory link (from my updated get_memory_neighborhood)
                    val = f"{item['entity']} ({item['predicate']})"
                    if val not in seen:
                        lines.append(f"- {val}")
                        seen.add(val)
            if lines:
                neighborhood_str = "\n".join(lines)

        return f"""
[ANALYSIS FOR: {topic}]

--- SUMMARIES ---
{summaries_str}

--- EPISODES ---
{episodes_str}

--- ENRICHED CONNECTIONS ---
{neighborhood_str}

--- FACTS ---
{facts_str}
"""
