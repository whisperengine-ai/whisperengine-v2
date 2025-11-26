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
