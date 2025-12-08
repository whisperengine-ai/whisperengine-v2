from typing import Type, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.universe.manager import universe_manager
from src_v2.core.database import db_manager
from src_v2.config.settings import settings

class CheckPlanetContextInput(BaseModel):
    reason: Optional[str] = Field(default=None, description="Optional reason for checking context")

class CheckPlanetContextTool(BaseTool):
    name: str = "planet_ctx"
    description: str = "Checks the current 'Planet' (Discord Server) for context. Returns the planet name, population, and list of known channels/locations. Use this when the user asks 'where are we?' or about the server."
    args_schema: Type[BaseModel] = CheckPlanetContextInput
    guild_id: Optional[str] = Field(exclude=True)

    def _run(self, reason: Optional[str] = None) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, reason: Optional[str] = None) -> str:
        if not self.guild_id:
            # This is expected for DMs or when guild_id wasn't passed
            # logger.warning("CheckPlanetContextTool called without guild_id (Private Void)")
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
    name: str = "universe"
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


class GetSiblingBotInfoInput(BaseModel):
    bot_name: Optional[str] = Field(
        default=None,
        description="Name of a specific sibling bot to get info about (e.g., 'dotty', 'elena'). Leave empty to list all known sibling bots."
    )


class GetSiblingBotInfoTool(BaseTool):
    """Get information about sibling bots in the WhisperEngine family."""
    name: str = "sibling_info"
    description: str = """Get information about other AI companions (sibling bots) in the WhisperEngine family.

USE THIS WHEN:
- User asks "who is Dotty?" or "do you know Elena?" or "tell me about [bot name]"
- User mentions another bot's name and you want to know more
- User asks "who are your friends?" or "what other bots do you know?"
- User shares a document about another bot and asks for analysis
- You want to recall past conversations with another bot

Returns: List of sibling bots, or detailed info about a specific bot including:
- Basic identity
- Your past conversations with them
- Shared knowledge and observations
- Their personality/character (if available)"""
    args_schema: Type[BaseModel] = GetSiblingBotInfoInput
    
    # Injected at runtime
    character_name: str = Field(default="", exclude=True)

    def _run(self, bot_name: Optional[str] = None) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, bot_name: Optional[str] = None) -> str:
        try:
            from src_v2.broadcast.cross_bot import cross_bot_manager
            
            # Get list of known bots
            known_bots = cross_bot_manager.known_bots
            
            if not known_bots:
                return "I don't have information about any sibling bots at the moment. They may not be online or registered yet."
            
            # Filter out self
            my_name = self.character_name.lower() if self.character_name else settings.DISCORD_BOT_NAME.lower()
            sibling_names = [name for name in known_bots.keys() if name.lower() != my_name]
            
            if not bot_name:
                # List all known siblings
                if not sibling_names:
                    return "I'm the only bot currently registered in the system."
                
                lines = ["🤖 MY SIBLING BOTS (WhisperEngine Family):"]
                for name in sorted(sibling_names):
                    lines.append(f"  • {name.title()}")
                lines.append(f"\nTotal: {len(sibling_names)} sibling bots")
                lines.append("\nUse get_sibling_bot_info with a specific name to learn more about any of them!")
                return "\n".join(lines)
            
            # Get info about a specific bot
            target_name = bot_name.lower().strip()
            
            # Check if this bot exists
            if target_name not in [n.lower() for n in known_bots.keys()] and target_name != my_name:
                # Could still have info from documents/memories even if bot isn't online
                pass  # Continue to check other sources
            
            lines = [f"🤖 SIBLING BOT INFO: {target_name.title()}"]
            
            # 1. Check if they're a known registered bot
            is_registered = target_name in [n.lower() for n in known_bots.keys()]
            target_discord_id = known_bots.get(target_name)
            
            if is_registered:
                lines.append(f"Status: Currently registered in the system ✓")
            else:
                lines.append(f"Status: Not currently online (but may still have memories of them)")
            
            # 2. Try to load their character info
            character_info = await self._get_character_info(target_name)
            if character_info:
                lines.append(f"\n📋 CHARACTER PROFILE:")
                lines.append(character_info)
            
            # 3. Get conversation history between us
            if target_discord_id and db_manager.postgres_pool:
                conversation_context = await self._get_conversation_history(
                    my_name, target_name, str(target_discord_id)
                )
                if conversation_context:
                    lines.append(f"\n💬 OUR CONVERSATION HISTORY:")
                    lines.append(conversation_context)
            
            # 4. Get shared knowledge from Neo4j
            if db_manager.neo4j_driver:
                shared_knowledge = await self._get_shared_knowledge(my_name, target_name)
                if shared_knowledge:
                    lines.append(f"\n🧠 WHAT I KNOW ABOUT THEM:")
                    lines.append(shared_knowledge)
            
            if len(lines) <= 2:
                lines.append(f"\nI don't have much information about {target_name.title()} yet. We may not have interacted much, or they might be a new sibling!")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"get_sibling_bot_info tool failed: {e}")
            return f"Error retrieving sibling bot info: {str(e)}"
    
    async def _get_character_info(self, bot_name: str) -> Optional[str]:
        """Try to load character info from the character files."""
        try:
            from pathlib import Path
            
            char_dir = Path("characters") / bot_name
            core_yaml = char_dir / "core.yaml"
            
            if core_yaml.exists():
                import yaml
                with open(core_yaml) as f:
                    core = yaml.safe_load(f)
                
                lines = []
                if core.get("identity", {}).get("purpose"):
                    lines.append(f"Purpose: {core['identity']['purpose']}")
                if core.get("identity", {}).get("role"):
                    lines.append(f"Role: {core['identity']['role']}")
                
                # Get a glimpse of personality
                drives = core.get("drives", [])
                if drives:
                    drive_names = [d.get("name", "") for d in drives[:3] if d.get("name")]
                    if drive_names:
                        lines.append(f"Driven by: {', '.join(drive_names)}")
                
                return "\n".join(lines) if lines else None
            
            return None
        except Exception as e:
            logger.debug(f"Could not load character info for {bot_name}: {e}")
            return None
    
    async def _get_conversation_history(
        self, my_name: str, target_name: str, target_discord_id: str
    ) -> Optional[str]:
        """Get recent conversation history with another bot."""
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Get recent messages between us
                history = await conn.fetch("""
                    SELECT role, content, timestamp
                    FROM v2_chat_history
                    WHERE user_id = $1 AND character_name = $2
                    ORDER BY timestamp DESC
                    LIMIT 6
                """, target_discord_id, my_name)
                
                if not history:
                    return None
                
                lines = []
                for row in reversed(history):
                    role = "Me" if row['role'] == 'assistant' else target_name.title()
                    content = row['content'][:100]
                    if len(row['content']) > 100:
                        content += "..."
                    # Format timestamp
                    ts = row['timestamp']
                    if hasattr(ts, 'strftime'):
                        ts_str = ts.strftime("%b %d")
                    else:
                        ts_str = "recently"
                    lines.append(f"[{ts_str}] {role}: {content}")
                
                # Get conversation count
                count = await conn.fetchval("""
                    SELECT COUNT(*) FROM v2_chat_history
                    WHERE user_id = $1 AND character_name = $2
                """, target_discord_id, my_name)
                
                if count > 6:
                    lines.insert(0, f"(Showing last 6 of {count} messages)")
                
                return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Could not get conversation history: {e}")
            return None
    
    async def _get_shared_knowledge(self, my_name: str, target_name: str) -> Optional[str]:
        """Get observations and knowledge about another bot from Neo4j."""
        try:
            async with db_manager.neo4j_driver.session() as session:
                # Find observations I've made about them
                query = """
                MATCH (c:Character {name: $my_name})-[o:OBSERVED]->(s)
                WHERE toLower(s.id) CONTAINS $target_lower
                   OR toLower(s.name) CONTAINS $target_lower
                RETURN o.content as observation, o.type as type
                ORDER BY o.timestamp DESC
                LIMIT 3
                """
                result = await session.run(
                    query, 
                    my_name=my_name.title(),
                    target_lower=target_name.lower()
                )
                records = await result.data()
                
                if not records:
                    return None
                
                lines = []
                for r in records:
                    if r.get('observation'):
                        obs = r['observation'][:150]
                        if len(r['observation']) > 150:
                            obs += "..."
                        lines.append(f"• {obs}")
                
                return "\n".join(lines) if lines else None
        except Exception as e:
            logger.debug(f"Could not get shared knowledge: {e}")
            return None
