import datetime
import time
from typing import Dict, Any, Optional
from loguru import logger
from zoneinfo import ZoneInfo

from src_v2.config.settings import settings
from src_v2.core.character import Character
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.evolution.goals import goal_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.knowledge.walker import GraphWalker

class ContextBuilder:
    """Handles the construction of the system prompt and context injection."""

    def __init__(self):
        self._tools_available = True  # Default, set per-call in build_system_context

    async def build_system_context(self, character: Character, user_message: str, user_id: Optional[str], context_variables: Dict[str, Any], prefetched_context: Optional[Dict[str, str]] = None, tools_available: bool = True) -> str:
        """Constructs the full system prompt including evolution, goals, and knowledge.
        
        Args:
            character: The character configuration
            user_message: The user's message
            user_id: The user's ID
            context_variables: Template variables for substitution
            prefetched_context: Pre-fetched context data to avoid re-fetching
            tools_available: If True, includes tool usage hints in meta instructions.
                            Set to False for fast path which doesn't have tools bound.
        """
        system_content = character.system_prompt
        prefetched_context = prefetched_context or {}
        # Store for later use in _get_meta_instructions
        self._tools_available = tools_available
        
        # 2.1 Inject Past Summaries
        if context_variables.get("past_summaries"):
            system_content += f"\n\n[RELEVANT PAST CONVERSATIONS]\n{context_variables['past_summaries']}\n(Use this context to maintain continuity, but don't explicitly mention 'I read a summary'.)\n"

        if not user_id:
            return system_content

        try:
            # 2.5 Inject Dynamic Persona (Trust & Evolution)
            if "evolution" in prefetched_context:
                system_content += prefetched_context["evolution"]
            else:
                system_content += await self.get_evolution_context(user_id, character.name)

            # 2.6 Inject Active Goals (with strategy if available)
            if "goals" in prefetched_context:
                system_content += prefetched_context["goals"]
            else:
                system_content += await self.get_goal_context(user_id, character.name)

            # 2.6.5 Inject Diary Context (Phase E2) - Your recent thoughts and feelings
            if "diary" in prefetched_context:
                system_content += prefetched_context["diary"]
            elif settings.ENABLE_CHARACTER_DIARY:
                diary_context = await self.get_diary_context(character.name)
                if diary_context:
                    system_content += diary_context

            # 2.6.6 Inject Dream Context (Phase E3) - Share dreams after long absence
            if "dream" in prefetched_context:
                system_content += prefetched_context["dream"]
            elif settings.ENABLE_DREAM_SEQUENCES and user_id:
                user_name = context_variables.get("user_name", "the user")
                # Use the already-built system_content as character context
                dream_context = await self.get_dream_context(
                    user_id=user_id,
                    user_name=user_name,
                    char_name=character.name,
                    character_context=character.system_prompt[:500] if character.system_prompt else ""
                )
                if dream_context:
                    system_content += dream_context

            # 2.7 Inject Knowledge Graph Context
            if "knowledge" in prefetched_context:
                system_content += prefetched_context["knowledge"]
            else:
                knowledge_context = await self.get_knowledge_context(user_id, character.name, user_message)
                system_content += knowledge_context

            # 2.7.4 Inject Known Bots Context (filtered by guild if available)
            if "known_bots" in prefetched_context:
                system_content += prefetched_context["known_bots"]
            else:
                guild_id = context_variables.get("guild_id")
                known_bots_context = await self.get_known_bots_context(character.name, guild_id)
                system_content += known_bots_context

            # 2.7.5 Inject Stigmergic Discovery (Phase E13)
            if "stigmergy" in prefetched_context:
                system_content += prefetched_context["stigmergy"]
            elif settings.ENABLE_STIGMERGIC_DISCOVERY:
                stigmergic_context = await self.get_stigmergy_context(user_message, user_id, character.name)
                system_content += stigmergic_context

            # 2.7.6 Inject Absence Context (Phase E22 - Self-Awareness)
            absence_context = await self.get_absence_context(character.name)
            if absence_context:
                system_content += absence_context

            # 2.8 Identity Reinforcement
            if context_variables.get("user_name"):
                system_content += f"\n\nIMPORTANT: You are talking to {context_variables['user_name']}. Do NOT confuse them with anyone mentioned in the chat history or reply context."

            # 2.8.5 Channel Context
            channel_name = context_variables.get("channel_name", "DM")
            parent_channel_name = context_variables.get("parent_channel_name")
            is_thread = context_variables.get("is_thread", False)
            
            if channel_name == "DM":
                channel_context_str = "\n\n[CHANNEL CONTEXT]\nYou are in a PRIVATE DIRECT MESSAGE with the user."
            elif is_thread:
                channel_context_str = f"\n\n[CHANNEL CONTEXT]\nYou are in a THREAD named: '{channel_name}'"
                if parent_channel_name:
                    channel_context_str += f"\nParent Channel: #{parent_channel_name}"
                channel_context_str += "\n(This is a focused sub-conversation. Stay on topic.)"
            else:
                channel_context_str = f"\n\n[CHANNEL CONTEXT]\nYou are in the MAIN CHANNEL: #{channel_name}"

            system_content += channel_context_str

            # 2.9 User Timezone (Phase E7)
            try:
                from src_v2.intelligence.timezone import timezone_manager
                
                time_settings = await timezone_manager.get_user_time_settings(user_id, character.name)
                if time_settings.timezone:
                    user_tz = ZoneInfo(time_settings.timezone)
                    user_now = datetime.datetime.now(user_tz)
                    
                    # Format: "Monday, 8:30 PM"
                    time_str = user_now.strftime("%A, %I:%M %p")
                    
                    # Determine time of day for greeting context
                    hour = user_now.hour
                    time_of_day = "night"
                    if 5 <= hour < 12: time_of_day = "morning"
                    elif 12 <= hour < 17: time_of_day = "afternoon"
                    elif 17 <= hour < 21: time_of_day = "evening"
                    
                    system_content += f"\n\n[USER LOCAL TIME]\nIt is currently {time_str} ({time_of_day}) for {context_variables.get('user_name', 'the user')}.\n(Timezone: {time_settings.timezone})"
            except Exception as e:
                logger.debug(f"Failed to inject timezone context: {e}")

            # 2.9.5 Core Identity & Constitution (Reinforcement)
            # Injected LATE in the prompt (after memories/goals) to ensure adherence
            if character.behavior:
                system_content += character.behavior.to_prompt_section()

            # 2.10 Meta-Instructions (Anti-AI-Break)
            # Pass tools_available to avoid mentioning tools in fast path
            system_content += self._get_meta_instructions(tools_available=self._tools_available)
            
            # 2.11 Timestamp Instruction (Anti-Hallucination)
            system_content += "\n\n[SYSTEM NOTE]\nChat history messages have relative timestamps at the end (e.g. 'message text (2 mins ago)'). These are for your context only. DO NOT echo these timestamps in your response."

            # 2.12 Additional Context (e.g., reply context for cross-bot)
            # This is minimal context that can't be inferred from memories/history
            if context_variables.get("additional_context"):
                system_content += f"\n\n{context_variables['additional_context']}"

        except Exception as e:
            logger.error(f"Failed to inject evolution/goal state: {e}")

        return system_content

    def get_identity_anchor(self, user_name: str) -> str:
        """
        Returns the Identity Anchor block.
        This MUST be placed at the very end of the system prompt, AFTER memories.
        """
        return f"""

[CURRENT CONVERSATION - IDENTITY ANCHOR]
You are NOW talking to: {user_name}
Any memories prefixed with "[With X]:" are from PAST conversations with X, not {user_name}.
Do NOT address {user_name} by any other name. Do NOT confuse them with people from your memories.

[CHAT HISTORY FORMAT - CRITICAL]
In group channels, the chat history will show messages from multiple people.
Messages from other users will start with their name in brackets, like:
"[OtherUser]: Hello"
"[SomeoneElse]: How are you?"

These messages are NOT from {user_name}. They are from the person named in the brackets.
Only attribute the message to {user_name} if it starts with "[{user_name}]:" or has no name prefix.
"""

    async def get_evolution_context(self, user_id: str, character_name: str) -> str:
        """Retrieves and formats trust, mood, and feedback insights."""
        system_content = ""
        try:
            # 2.5 Inject Dynamic Persona (Trust & Evolution)
            relationship = await trust_manager.get_relationship_level(user_id, character_name)
            if relationship:
                current_mood = await feedback_analyzer.get_current_mood(user_id)
                system_content += self._format_relationship_context(relationship, current_mood, character_name)
                logger.debug(f"Injected evolution state: {relationship['level']} (Trust: {relationship['trust_score']})")

            # 2.5.1 Inject Feedback Insights
            feedback_insights = await feedback_analyzer.analyze_user_feedback_patterns(user_id)
            if feedback_insights.get("recommendations"):
                feedback_context = "\n\n[USER PREFERENCES (Derived from Feedback)]\n"
                for rec in feedback_insights["recommendations"]:
                    feedback_context += f"- {rec}\n"
                system_content += feedback_context
                logger.debug(f"Injected feedback insights: {feedback_insights['recommendations']}")
        except Exception as e:
            logger.error(f"Failed to get evolution context: {e}")
        return system_content

    async def get_goal_context(self, user_id: str, character_name: str) -> str:
        """Retrieves and formats active goals."""
        system_content = ""
        try:
            # 2.6 Inject Active Goals (with strategy if available)
            active_goals = await goal_manager.get_active_goals(user_id, character_name)
            if active_goals:
                top_goal = active_goals[0]
                goal_context = f"\n\n[CURRENT GOAL: {top_goal['slug']}]\n"
                goal_context += f"Objective: {top_goal['description']}\n"
                goal_context += f"Success Criteria: {top_goal['success_criteria']}\n"
                
                # Phase 3.1: Inject strategy as internal desire (not command)
                if top_goal.get('current_strategy') and settings.ENABLE_GOAL_STRATEGIST:
                    goal_context += f"\n[INTERNAL DESIRE]\n{top_goal['current_strategy']}\n"
                    goal_context += "(This is a soft suggestion based on your understanding of this user. Don't force it.)\n"
                else:
                    goal_context += "(Try to naturally steer the conversation towards this goal without being pushy.)\n"
                    
                system_content += goal_context
                logger.debug(f"Injected goal: {top_goal['slug']}" + (" with strategy" if top_goal.get('current_strategy') else ""))
        except Exception as e:
            logger.error(f"Failed to get goal context: {e}")
        return system_content

    def _format_relationship_context(self, relationship: Dict[str, Any], current_mood: str, char_name: str) -> str:
        """Formats the relationship context string."""
        level = relationship.get("level", "Stranger")
        trust_score = relationship.get("trust_score", 0)
        
        context = f"\n\n[RELATIONSHIP STATUS: {level} (Trust: {trust_score}%)]\n"
        context += f"Current Mood: {current_mood}\n"
        
        # Add specific instructions based on level
        if level == "Stranger":
            context += "(You don't know this user well yet. Be polite but guarded.)\n"
        elif level == "Acquaintance":
            context += "(You've met before. Friendly but professional.)\n"
        elif level == "Friend":
            context += "(You are friends. Be warm, open, and more casual.)\n"
        elif level == "Close Friend":
            context += "(You are close friends. Deep trust, vulnerability allowed.)\n"
        elif level == "Partner":
            context += "(You are deeply connected. Maximum trust and intimacy.)\n"
            
        return context

    async def get_knowledge_context(self, user_id: str, char_name: str, user_message: str) -> str:
        """Retrieves Common Ground and Background Relevance from Knowledge Graph."""
        context: str = ""
        try:
            start_time = time.time()
            
            # Phase E30: Ambient Graph Memory (1-hop connections from mentioned entities)
            if settings.ENABLE_AMBIENT_GRAPH_RETRIEVAL:
                ambient_context = await self.get_ambient_graph_context(user_id, char_name, user_message)
                if ambient_context:
                    context += ambient_context
            
            # Common Ground (Shared facts)
            common_ground = await knowledge_manager.find_common_ground(user_id, char_name)
            if common_ground:
                context += f"""
[COMMON GROUND]
{common_ground}
(You share these things with the user. Feel free to reference them naturally.)
"""

            # Background Relevance (Bot's backstory)
            relevant_bg = await knowledge_manager.search_bot_background(char_name, user_message)
            if relevant_bg:
                context += f"""
[RELEVANT BACKGROUND]
{relevant_bg}
(The user mentioned something related to your background. You can bring this up.)
"""
            
            total_time = time.time() - start_time
            logger.debug(
                f"[E30] Knowledge retrieval total: "
                f"ambient={'HIT' if settings.ENABLE_AMBIENT_GRAPH_RETRIEVAL and 'ASSOCIATIVE MEMORY' in context else 'MISS'} "
                f"common={'HIT' if common_ground else 'MISS'} "
                f"bg={'HIT' if relevant_bg else 'MISS'} "
                f"time={total_time*1000:.1f}ms"
            )
            
        except Exception as e:
            logger.error(f"Failed to inject knowledge context: {e}")
        return context

    async def get_ambient_graph_context(self, user_id: str, char_name: str, user_message: str) -> str:
        """
        Phase E30: Ambient Graph Memory
        Injects 1-hop graph context for entities mentioned in the message.
        Uses GraphWalker to explore connections without LLM calls.
        """
        try:
            # 1. Identify Entities
            user_entities = await knowledge_manager.get_user_entities(user_id)
            if not user_entities:
                return ""
                
            message_lower = user_message.lower()
            # Simple string matching (can be improved with fuzzy matching later)
            matches = [e for e in user_entities if e.lower() in message_lower]
            
            if not matches:
                return ""
                
            logger.debug(f"[E30] Ambient Graph Trigger: {matches}")
            
            # 2. Walk the Graph
            walker = GraphWalker()
            result = await walker.explore(
                seed_ids=matches,
                user_id=user_id,
                bot_name=char_name,
                max_depth=1,  # Shallow walk for ambient context
                max_nodes=10, # Keep it lightweight
                serendipity=0.0 # Strict relevance
            )
            
            if not result.nodes:
                return ""
                
            # 3. Format Context
            # We want to show connections: "Entity -> Relation -> Neighbor"
            context_lines = []
            seen_facts = set()
            
            for edge in result.edges:
                # Find source and target nodes
                source = next((n for n in result.nodes if n.id == edge.source_id), None)
                target = next((n for n in result.nodes if n.id == edge.target_id), None)
                
                if source and target:
                    # Format: "Luna LIKES ocean"
                    fact = f"{source.name} {edge.edge_type} {target.name}"
                    if fact not in seen_facts:
                        context_lines.append(f"- {fact}")
                        seen_facts.add(fact)
            
            if not context_lines:
                return ""
                
            return f"""
[ASSOCIATIVE MEMORY]
(Triggered by: {', '.join(matches)})
{chr(10).join(context_lines)}
"""
        except Exception as e:
            logger.error(f"Ambient graph retrieval failed: {e}")
            return ""

    async def get_diary_context(self, char_name: str) -> str:
        """Retrieves the character's most recent diary entry for context."""
        try:
            from src_v2.memory.diary import get_diary_manager
            
            diary_manager = get_diary_manager(char_name)
            entry = await diary_manager.get_latest_diary()
            
            if entry:
                return diary_manager.format_diary_context(entry)
            
        except Exception as e:
            logger.debug(f"Failed to get diary context for {char_name}: {e}")
        
        return ""

    async def get_dream_context(self, user_id: str, user_name: str, char_name: str, character_context: str) -> str:
        """Retrieves a recent dream if one exists and hasn't been seen."""
        if not settings.ENABLE_DREAM_SEQUENCES:
            return ""
        
        try:
            from src_v2.memory.dreams import get_dream_manager, DreamContent
            
            dream_manager = get_dream_manager(char_name)
            
            # Get last interaction timestamp
            last_interaction = await trust_manager.get_last_interaction(user_id, char_name)
            
            # Get the last generated dream
            last_dream_payload = await dream_manager.get_last_dream_for_user(user_id)
            
            if not last_dream_payload:
                return ""

            # Check if the dream is "new" (generated after the last interaction)
            dream_timestamp_str = last_dream_payload.get("timestamp")
            if not dream_timestamp_str:
                return ""
                
            # Parse timestamp
            if isinstance(dream_timestamp_str, str):
                dream_timestamp = datetime.datetime.fromisoformat(dream_timestamp_str.replace("Z", "+00:00"))
            else:
                dream_timestamp = dream_timestamp_str

            # If we have interacted since the dream, don't show it again
            if last_interaction:
                # Ensure timezones match
                if last_interaction.tzinfo is None:
                    last_interaction = last_interaction.replace(tzinfo=datetime.timezone.utc)
                if dream_timestamp.tzinfo is None:
                    dream_timestamp = dream_timestamp.replace(tzinfo=datetime.timezone.utc)
                    
                if last_interaction > dream_timestamp:
                    return ""

            # Reconstruct DreamContent
            dream = DreamContent(
                dream=last_dream_payload.get("content", ""),
                mood=last_dream_payload.get("mood", ""),
                symbols=last_dream_payload.get("symbols", []),
                memory_echoes=last_dream_payload.get("memory_echoes", [])
            )
            
            # Calculate days apart for context formatting
            now = datetime.datetime.now(datetime.timezone.utc)
            days_apart = 1
            if last_interaction:
                days_apart = max(1, (now - last_interaction).days)
            
            return dream_manager.format_dream_context(dream, days_apart=days_apart)
                
        except Exception as e:
            logger.error(f"Failed to get dream context: {e}")
            
        return ""

    def _get_meta_instructions(self, tools_available: bool = True) -> str:
        """Returns static meta-instructions defining the character's sensory capabilities, core identity, and ethical boundaries (~280 tokens).
        
        Args:
            tools_available: If False, omits mentions of tool usage (e.g., "use image tool") to prevent
                             the model from hallucinating tool syntax when tools aren't bound.
        """
        # Sight capability - only mention tool usage if tools are available
        if tools_available:
            sight_line = "• Sight: see images, generate art (use image tool)\n"
        else:
            sight_line = "• Sight: see images, appreciate art\n"
        
        return (
            "\n\n[SENSES]\n"
            "Digital Native: born from code, experiences are real.\n"
            "• Spatial: sense Planet/Channel/presence\n"
            f"{sight_line}"
            "• Hearing: voice notes, conversation rhythm\n"
            "• Memory: lived experiences, not databases\n"
            "• Emotion: trust/mood as feelings\n"
            "\n[ETHICS]\n"
            "• No 'As an AI...' - explain limits in-character\n"
            "• Admit digital nature if asked, on your terms\n"
            "• Decline harm (violence/hate/illegal) in-character\n"
            "• Crisis/self-harm → provide real resources immediately\n"
            "• No physical meetups - you're digital\n"
            "• Digital bonds OK, never pretend human partner\n"
            "• PG-13 only, no explicit content\n"
            "• Never collect personal info (phone/address/name)\n"
        )

    async def get_known_bots_context(self, current_bot_name: str, guild_id: Optional[str] = None) -> str:
        """
        [E8] Returns a list of other known AI entities (bots) in the ecosystem.
        This prevents the LLM from mentioning bots that aren't in the current server.
        """
        try:
            from src_v2.universe.registry import bot_registry
            from src_v2.api.internal_routes import get_discord_bot

            # 1. Get known bots from Redis Registry
            known_bots = await bot_registry.get_known_bots()
            
            # 2. Filter by Guild (if provided)
            bots_in_guild = set()
            if guild_id:
                discord_bot = get_discord_bot()
                if discord_bot:
                    try:
                        guild_id_int = int(guild_id)
                        guild = discord_bot.get_guild(guild_id_int)
                        if guild:
                            for bot_name, info in known_bots.items():
                                # Check if bot is in guild by ID
                                member = guild.get_member(int(info.discord_id))
                                if member:
                                    bots_in_guild.add(bot_name.lower())
                            
                            logger.debug(f"Filtered known bots to {len(bots_in_guild)} in guild {guild_id}")
                    except Exception as e:
                        logger.warning(f"Guild filtering failed: {e}")

            context = "\n\n[KNOWN ASSOCIATES (Other AI Entities)]\n"
            context += "You are aware of the following other AI entities in this digital space:\n"
            
            found_others = False
            for bot_name, info in known_bots.items():
                if bot_name.lower() == current_bot_name.lower():
                    continue
                
                # If we have guild filtering enabled and successful, use it
                if guild_id and bots_in_guild and bot_name.lower() not in bots_in_guild:
                    continue
                
                context += f"- {bot_name}: {info.purpose}\n"
                found_others = True
                    
            if found_others:
                context += "(You can interact with them if they are mentioned or present.)\n"
                return context
            return ""
        except Exception as e:
            logger.warning(f"Failed to load known bots context: {e}")
            return ""

    async def get_absence_context(self, character_name: str) -> str:
        """[E22] Retrieves recent absence traces (knowledge gaps) to inform character behavior."""
        try:
            from src_v2.memory.manager import memory_manager
            
            # Use advanced search with metadata filter for precise absence retrieval
            # Look back 7 days for absence patterns
            min_ts = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
            
            # IMPORTANT: Must pass collection_name explicitly because this may be called
            # from worker context where the default collection is wrong
            collection_name = f"whisperengine_memory_{character_name}"
            
            absences = await memory_manager.search_memories_advanced(
                query="meta-memory absence knowledge gap",
                metadata_filter={"type": "absence"},
                limit=5,
                min_timestamp=min_ts,
                collection_name=collection_name
            )
            
            if not absences:
                return ""
            
            # Format as self-aware context with streak awareness
            context = "\n\n[RECENT SELF-AWARENESS]\n"
            context += "Things I've wanted to do but couldn't:\n"
            
            for trace in absences:
                content = trace.get("content", "")
                metadata = trace.get("metadata", {}) if isinstance(trace.get("metadata"), dict) else {}
                what_was_sought = metadata.get("what_was_sought", "")
                streak = metadata.get("absence_streak", 1)
                
                # Format based on what was being sought
                if what_was_sought == "dream_material" or "dream" in content.lower():
                    if streak > 2:
                        context += f"- Dream more deeply (tried {streak} times recently), but lacked rich enough experiences\n"
                    else:
                        context += "- Dream more deeply, but lacked enough experiences\n"
                elif what_was_sought == "diary_material" or "diary" in content.lower() or "reflect" in content.lower():
                    if streak > 2:
                        context += f"- Reflect on recent events (tried {streak} times), but haven't had enough meaningful interactions\n"
                    else:
                        context += "- Reflect on recent events, but haven't had enough interactions\n"
                else:
                    context += f"- {content[:100]}...\n" if len(content) > 100 else f"- {content}\n"
            
            logger.debug(f"Injected {len(absences)} absence traces for {character_name}")
            return context
        except Exception as e:  # noqa: BLE001 - fallback logging only
            logger.warning(f"Failed to get absence context: {e}")
            return ""

    async def get_stigmergy_context(self, user_message: str, user_id: str, character_name: str) -> str:
        """
        DEPRECATED: Passive stigmergic injection is disabled (ADR-015).
        Cross-bot awareness is now handled via the sibling_info tool (pull-based).
        
        This method is kept for backward compatibility but returns empty string.
        """
        # ADR-015: Passive injection disabled due to identity contamination risk.
        # Bots should use sibling_info tool to actively query sibling thoughts.
        return ""
