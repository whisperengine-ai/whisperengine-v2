from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.universe.manager import universe_manager

class CheckPlanetContextInput(BaseModel):
    pass # No input needed, it uses the current guild_id from context

class CheckPlanetContextTool(BaseTool):
    name: str = "check_planet_context"
    description: str = "Checks the current 'Planet' (Discord Server) for context. Returns the planet name, population, and list of known channels/locations. Use this when the user asks 'where are we?' or about the server."
    args_schema: Type[BaseModel] = CheckPlanetContextInput
    guild_id: Optional[str] = Field(exclude=True)

    def _run(self) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> str:
        if not self.guild_id:
            logger.warning("CheckPlanetContextTool called without guild_id (Private Void)")
            return "We are currently in a private void (Direct Message). No planet context available."
        
        try:
            context = await universe_manager.get_planet_context(self.guild_id)
            if not context:
                return "Planet data not found in the archives."
            
            return (
                f"PLANET: {context['name']}\n"
                f"INHABITANTS: {context['inhabitant_count']} known souls\n"
                f"LOCATIONS (Channels): {', '.join(context['channels'])}\n"
            )
        except Exception as e:
            return f"Error checking planet context: {e}"


class GetUniverseOverviewInput(BaseModel):
    pass  # No input needed, returns global universe state

class GetUniverseOverviewTool(BaseTool):
    name: str = "get_universe_overview"
    description: str = """Get a comprehensive overview of ALL planets, channels, and inhabitants across the entire universe. 
    Use this when the user asks about what's happening 'everywhere', 'across all planets', 'in the universe', or wants you to tell another bot about the universe state.
    Returns: planet count, list of planets with their channels/topics/inhabitants, and top topics across the universe."""
    args_schema: Type[BaseModel] = GetUniverseOverviewInput

    def _run(self) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> str:
        try:
            data = await universe_manager.get_universe_overview()
            
            if data.get("error"):
                return f"⚠️ {data['error']}"
            
            # Format the response for the LLM
            lines = []
            lines.append("🌌 UNIVERSE OVERVIEW")
            lines.append(f"Active Planets: {data['planet_count']}")
            lines.append(f"Total Inhabitants: {data['total_inhabitants']} souls across the cosmos\n")
            
            if data.get("top_universal_topics"):
                lines.append(f"🔥 Hot Topics Universe-Wide: {', '.join(data['top_universal_topics'][:5])}\n")
            
            lines.append("📍 PLANETS:")
            for planet in data.get("planets", []):
                lines.append(f"\n  • {planet['name']} ({planet['inhabitant_count']} inhabitants)")
                if planet.get("channels"):
                    channels_preview = planet["channels"][:5]
                    channels_str = ", ".join(channels_preview)
                    if planet["channel_count"] > 5:
                        channels_str += f" (+{planet['channel_count'] - 5} more)"
                    lines.append(f"    Channels: {channels_str}")
                if planet.get("top_topics"):
                    lines.append(f"    Topics: {', '.join(planet['top_topics'][:3])}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"get_universe_overview tool failed: {e}")
            return f"Error retrieving universe overview: {str(e)}"

class GetRecentActivityInput(BaseModel):
    pass

class GetRecentActivityTool(BaseTool):
    name: str = "get_recent_activity"
    description: str = "Gets the recent messages and activity in the current channel. Use this when asked 'what happened recently?', 'what did X say?', or 'catch me up'."
    args_schema: Type[BaseModel] = GetRecentActivityInput
    channel_context: str = Field(default="", exclude=True)

    def _run(self) -> str:
        return self.channel_context or "No recent activity found in context."

    async def _arun(self) -> str:
        return self._run()

