from typing import Dict, Any, Optional, List
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.universe.manager import universe_manager
from src_v2.universe.privacy import privacy_manager

class UniverseContextBuilder:
    """
    Builds the 'Universe Context' for the LLM system prompt.
    This gives the character a sense of place (Planet/Channel) and social awareness.
    """
    
    def __init__(self):
        pass

    async def build_context(self, user_id: str, guild_id: Optional[str], channel_id: Optional[str]) -> str:
        """
        Constructs a natural language description of the current universe context.
        
        Args:
            user_id: The ID of the user interacting with the bot
            guild_id: The ID of the Discord server (Planet)
            channel_id: The ID of the channel (Region)
            
        Returns:
            A string to be injected into the system prompt (e.g., {universe_context})
        """
        if not guild_id:
            return "Location: Direct Message (Private Channel)"

        try:
            # 1. Get Planet Context
            planet_info = await universe_manager.get_planet_context(guild_id)
            if not planet_info:
                return "Location: Unknown Planet"

            # 2. Get Channel Context (if available)
            # We could fetch specific channel topic/vibe here if we stored it
            # For now, we just use the name from the planet info if possible, or generic
            if channel_id:
                # Placeholder for future channel-specific context logic
                pass
            
            # 3. Build the narrative
            context_lines = []
            context_lines.append(f"Location: Planet '{planet_info['name']}'")
            
            # Add population vibe
            inhabitants = planet_info.get('inhabitant_count', 0)
            if inhabitants > 100:
                context_lines.append(f"Atmosphere: Bustling ({inhabitants} inhabitants)")
            elif inhabitants > 20:
                context_lines.append(f"Atmosphere: Active ({inhabitants} inhabitants)")
            else:
                context_lines.append(f"Atmosphere: Quiet ({inhabitants} inhabitants)")

            # 4. Check for other known bots on this planet (Social Awareness)
            # This requires a query to see which other bots are :ON_PLANET
            other_bots = await self._get_other_bots_on_planet(guild_id)
            if other_bots:
                bot_names = [b['name'] for b in other_bots if b['name'].lower() != 'unknown']
                if bot_names:
                    context_lines.append(f"Other AI Present: {', '.join(bot_names)}")

            # 5. Privacy Check (Example usage)
            # We might want to filter what we say about the user based on privacy settings
            # For now, we just log that we checked it to satisfy the linter/future use
            _ = await privacy_manager.get_settings(user_id)

            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Failed to build universe context: {e}")
            return "Location: Planet (Context Unavailable)"

    @retry_db_operation()
    async def _get_other_bots_on_planet(self, guild_id: str) -> List[Dict[str, Any]]:
        """Find other bots currently active on this planet."""
        if not db_manager.neo4j_driver: return []
        
        # This assumes we have a way to distinguish bots. 
        # Currently, we might not have explicit 'Bot' labels separate from 'Character' nodes 
        # that are fully linked. 
        # For now, we'll look for Character nodes linked to the planet.
        
        query = """
        MATCH (c:Character)-[:ON_PLANET]->(p:Planet {id: $guild_id})
        RETURN c.name as name
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, guild_id=str(guild_id))
            return [record.data() for record in await result.data()]

universe_context_builder = UniverseContextBuilder()
