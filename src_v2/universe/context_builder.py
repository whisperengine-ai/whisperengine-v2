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
        self._current_character: Optional[str] = None

    async def build_context(
        self, 
        user_id: str, 
        guild_id: Optional[str], 
        channel_id: Optional[str],
        character_name: Optional[str] = None
    ) -> str:
        """
        Constructs a natural language description of the current universe context.
        
        Args:
            user_id: The ID of the user interacting with the bot
            guild_id: The ID of the Discord server (Planet)
            channel_id: The ID of the channel (Region)
            character_name: Name of the current character (for relationship context)
            
        Returns:
            A string to be injected into the system prompt (e.g., {universe_context})
        """
        self._current_character = character_name
        
        if not guild_id:
            # DM - still include relationship context
            context_lines = ["Current Connection: Direct Message (Private Channel)"]
            
            # Add relationship context even in DMs
            if character_name:
                relationship_context = await self._build_relationship_context(character_name, user_id)
                if relationship_context:
                    context_lines.append("")
                    context_lines.append(relationship_context)
            
            return "\n".join(context_lines)

        try:
            # 1. Get Planet Context
            planet_info = await universe_manager.get_planet_context(guild_id)
            if not planet_info:
                return "Location: Unknown Planet"

            # 2. Build the narrative
            context_lines = []
            context_lines.append(f"Current Connection: Planet '{planet_info['name']}'")
            
            # Add population vibe
            inhabitants = planet_info.get('inhabitant_count', 0)
            if inhabitants > 100:
                context_lines.append(f"Atmosphere: Bustling ({inhabitants} inhabitants)")
            elif inhabitants > 20:
                context_lines.append(f"Atmosphere: Active ({inhabitants} inhabitants)")
            else:
                context_lines.append(f"Atmosphere: Quiet ({inhabitants} inhabitants)")

            # 3. Add planet topics if available
            topics = await universe_manager.get_planet_topics(guild_id, limit=5)
            if topics:
                topic_names = [t['name'] for t in topics[:5]]
                context_lines.append(f"Hot Topics: {', '.join(topic_names)}")

            # 4. Add peak hours if available
            peak_hours = await universe_manager.get_planet_peak_hours(guild_id)
            if peak_hours:
                peak_str = ", ".join([f"{h}:00" for h in peak_hours])
                context_lines.append(f"Peak Activity: {peak_str}")

            # 5. Check for other known bots on this planet (Social Awareness)
            other_bots = await self._get_other_bots_on_planet(guild_id)
            if other_bots:
                bot_names = [b['name'] for b in other_bots if b['name'].lower() != 'unknown']
                if character_name:
                    # Exclude self
                    bot_names = [n for n in bot_names if n.lower() != character_name.lower()]
                if bot_names:
                    context_lines.append(f"Other Travelers Here: {', '.join(bot_names)}")

            # 6. Add relationship context (what you know about this user)
            if character_name:
                privacy_settings = await privacy_manager.get_settings(user_id)
                
                # Check if user allows cross-bot sharing
                include_cross_bot = privacy_settings.get('share_with_other_bots', True)
                
                if not privacy_settings.get('invisible_mode', False):
                    relationship_context = await self._build_relationship_context(
                        character_name, 
                        user_id,
                        include_cross_bot=include_cross_bot
                    )
                    if relationship_context:
                        context_lines.append("")
                        context_lines.append("[Your Relationship with This User]")
                        context_lines.append(relationship_context)

                    # 7. Social Circle (Who they hang out with on this planet)
                    # Only if not invisible
                    interactions = await universe_manager.get_user_interactions(user_id, guild_id, limit=3)
                    if interactions:
                        # We have user IDs, but we need names. 
                        # Since we don't have easy access to Discord API here, we rely on what's in the graph.
                        # Ideally, get_user_interactions should return display_name too.
                        # For now, we'll just list the count of close contacts.
                        contact_count = len(interactions)
                        context_lines.append(f"Social Circle: Interacts frequently with {contact_count} other inhabitants here.")

                    # 8. Potential Introductions (If enabled)
                    if privacy_settings.get('allow_bot_introductions', False):
                        introductions = await self._get_introductions(user_id, guild_id)
                        if introductions:
                            context_lines.append("")
                            context_lines.append("[Potential Introductions]")
                            context_lines.append(f"You might introduce them to: {introductions}")

            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Failed to build universe context: {e}")
            return "Location: Planet (Context Unavailable)"

    async def _get_introductions(self, user_id: str, guild_id: str) -> str:
        """Find users to introduce based on shared interests."""
        try:
            candidates = await universe_manager.find_potential_introductions(user_id, guild_id)
            valid_intros = []
            
            for cand in candidates:
                cand_id = cand['user_id']
                display_name = cand.get('display_name', 'Someone')
                shared_interests = cand.get('shared_interests', [])
                
                # Check candidate's privacy
                settings = await privacy_manager.get_settings(cand_id)
                if settings.get('allow_bot_introductions', False) and not settings.get('invisible_mode', False):
                    interests_str = ", ".join(shared_interests[:3])
                    valid_intros.append(f"{display_name} (likes {interests_str})")
            
            return ", ".join(valid_intros)
        except Exception as e:
            logger.debug(f"Failed to get introductions: {e}")
            return ""

    async def _build_relationship_context(
        self, 
        character_name: str, 
        user_id: str,
        include_cross_bot: bool = True
    ) -> str:
        """Build context about the relationship between this character and user."""
        try:
            return await universe_manager.build_relationship_context(
                character_name=character_name,
                user_id=user_id,
                include_cross_bot=include_cross_bot
            )
        except Exception as e:
            logger.debug(f"Failed to build relationship context: {e}")
            return ""

    @retry_db_operation()
    async def _get_other_bots_on_planet(self, guild_id: str) -> List[Dict[str, Any]]:
        """Find other bots currently active on this planet."""
        if not db_manager.neo4j_driver: return []
        
        query = """
        MATCH (c:Character)-[:KNOWS_USER]->(:User)-[:ON_PLANET]->(p:Planet {id: $guild_id})
        RETURN DISTINCT c.name as name
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, guild_id=str(guild_id))
            return [record.data() for record in await result.data()]

universe_context_builder = UniverseContextBuilder()
