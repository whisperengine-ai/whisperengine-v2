import datetime
from typing import Dict, Any, Optional, List
from loguru import logger
from zoneinfo import ZoneInfo

from src_v2.config.settings import settings
from src_v2.core.character import Character
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.evolution.goals import goal_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.manager import get_evolution_manager

class ContextBuilder:
    """Handles the construction of the system prompt and context injection."""

    def __init__(self):
        pass

    async def build_system_context(self, character: Character, user_message: str, user_id: Optional[str], context_variables: Dict[str, Any]) -> str:
        """Constructs the full system prompt including evolution, goals, and knowledge."""
        system_content = character.system_prompt
        
        # 2.1 Inject Past Summaries
        if context_variables.get("past_summaries"):
            system_content += f"\n\n[RELEVANT PAST CONVERSATIONS]\n{context_variables['past_summaries']}\n(Use this context to maintain continuity, but don't explicitly mention 'I read a summary'.)\n"

        if not user_id:
            return system_content

        try:
            # 2.5 Inject Dynamic Persona (Trust & Evolution)
            relationship = await trust_manager.get_relationship_level(user_id, character.name)
            if relationship:
                current_mood = await feedback_analyzer.get_current_mood(user_id)
                system_content += self._format_relationship_context(relationship, current_mood, character.name)
                logger.debug(f"Injected evolution state: {relationship['level']} (Trust: {relationship['trust_score']})")

            # 2.5.1 Inject Feedback Insights
            feedback_insights = await feedback_analyzer.analyze_user_feedback_patterns(user_id)
            if feedback_insights.get("recommendations"):
                feedback_context = "\n\n[USER PREFERENCES (Derived from Feedback)]\n"
                for rec in feedback_insights["recommendations"]:
                    feedback_context += f"- {rec}\n"
                system_content += feedback_context
                logger.debug(f"Injected feedback insights: {feedback_insights['recommendations']}")
            
            # 2.6 Inject Active Goals (with strategy if available)
            active_goals = await goal_manager.get_active_goals(user_id, character.name)
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

            # 2.6.5 Inject Diary Context (Phase E2) - Your recent thoughts and feelings
            if settings.ENABLE_CHARACTER_DIARY:
                diary_context = await self._get_diary_context(character.name)
                if diary_context:
                    system_content += diary_context

            # 2.6.6 Inject Dream Context (Phase E3) - Share dreams after long absence
            if settings.ENABLE_DREAM_SEQUENCES and user_id:
                user_name = context_variables.get("user_name", "the user")
                # Use the already-built system_content as character context
                dream_context = await self._get_dream_context(
                    user_id=user_id,
                    user_name=user_name,
                    char_name=character.name,
                    character_context=character.system_prompt[:500] if character.system_prompt else ""
                )
                if dream_context:
                    system_content += dream_context

            # 2.7 Inject Knowledge Graph Context
            knowledge_context = await self._get_knowledge_context(user_id, character.name, user_message)
            system_content += knowledge_context

            # 2.7.4 Inject Known Bots Context
            known_bots_context = await self._get_known_bots_context(character.name)
            system_content += known_bots_context

            # 2.7.5 Inject Stigmergic Discovery (Phase E13)
            if settings.ENABLE_STIGMERGIC_DISCOVERY:
                from src_v2.memory.shared_artifacts import shared_artifact_manager
                other_bot_insights = await shared_artifact_manager.discover_artifacts(
                    query=user_message,
                    artifact_types=["epiphany", "observation"],
                    exclude_bot=character.name,
                    user_id=user_id,
                    limit=settings.STIGMERGIC_DISCOVERY_LIMIT
                )
                
                if other_bot_insights:
                    stigmergic_context = "\n\n[INSIGHTS FROM OTHER CHARACTERS]\n"
                    for insight in other_bot_insights:
                        source = (insight.get("source_bot") or "unknown").title()
                        content = insight.get("content", "")[:200]
                        stigmergic_context += f"- {source} noticed: {content}\n"
                    system_content += stigmergic_context
                    logger.debug(f"Injected {len(other_bot_insights)} shared artifacts")

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

            # 2.10 Meta-Instructions (Anti-AI-Break)
            system_content += self._get_meta_instructions()
            
            # 2.11 Timestamp Instruction (Anti-Hallucination)
            system_content += "\n\n[SYSTEM NOTE]\nChat history messages are prefixed with relative timestamps (e.g. [2 mins ago]). These are for your context only. DO NOT generate these timestamps in your response."

        except Exception as e:
            logger.error(f"Failed to inject evolution/goal state: {e}")

        return system_content

    def _format_relationship_context(self, relationship: Dict[str, Any], current_mood: str, character_name: str) -> str:
        """Formats the relationship/trust context string."""
        trust_score = relationship.get('trust_score', 0)
        
        # Use EvolutionManager to build context
        evo_manager = get_evolution_manager(character_name)
        
        # current_mood represents USER's sentiment toward the bot (based on recent reactions)
        # NOT the bot's mood. Used to suppress traits (e.g., don't tease if user is frustrated)
        # FeedbackAnalyzer.get_current_mood() returns: "Happy", "Neutral", "Annoyed", "Excited"
        user_sentiment = "neutral"
        if "Annoyed" in current_mood: user_sentiment = "angry"
        elif "Happy" in current_mood or "Excited" in current_mood: user_sentiment = "happy"
        
        context = evo_manager.build_evolution_context(trust_score, user_sentiment)
        
        # Append Insights and Preferences (which are still in relationship dict)
        # Limit to most recent 7 insights to avoid bloating the prompt
        if relationship.get('insights'):
            insights = relationship['insights']
            # Take the last 7 (most recent) insights
            recent_insights = insights[-7:] if len(insights) > 7 else insights
            context += "\n[USER INSIGHTS]\n"
            for insight in recent_insights:
                context += f"- {insight}\n"
            context += "(These are deep psychological observations about the user. Use them to empathize and connect.)\n"

        if relationship.get('preferences'):
            context += "\n[USER CONFIGURATION]\n"
            prefs = relationship['preferences']
            
            if 'verbosity' in prefs:
                v = prefs['verbosity']
                if v == 'short': context += "- RESPONSE LENGTH: Keep responses very concise (1-2 sentences max).\n"
                elif v == 'medium': context += "- RESPONSE LENGTH: Keep responses moderate (2-4 sentences).\n"
                elif v == 'long': context += "- RESPONSE LENGTH: You may provide detailed, comprehensive responses.\n"
                elif v == 'dynamic': context += "- RESPONSE LENGTH: Adjust length based on context and user's input length.\n"
                else: context += f"- verbosity: {v}\n"
            
            if 'style' in prefs:
                s = prefs['style']
                if s == 'casual': context += "- TONE: Use casual, relaxed language. Slang is okay if fits character.\n"
                elif s == 'formal': context += "- TONE: Maintain a formal, polite, and professional tone.\n"
                elif s == 'matching': context += "- TONE: Mirror the user's energy and formality level.\n"
                else: context += f"- style: {s}\n"

        return context

    async def _get_knowledge_context(self, user_id: str, char_name: str, user_message: str) -> str:
        """Retrieves Common Ground and Background Relevance from Knowledge Graph."""
        context: str = ""
        try:
            common_ground = await knowledge_manager.find_common_ground(user_id, char_name)
            if common_ground:
                context += f"\n[COMMON GROUND]\n{common_ground}\n(You share these things with the user. Feel free to reference them naturally.)\n"
            
            relevant_bg = await knowledge_manager.search_bot_background(char_name, user_message)
            if relevant_bg:
                context += f"\n[RELEVANT BACKGROUND]\n{relevant_bg}\n(The user mentioned something related to your background. You can bring this up.)\n"
        except Exception as e:
            logger.error(f"Failed to inject knowledge context: {e}")
        return context

    async def _get_diary_context(self, char_name: str) -> str:
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

    async def _get_dream_context(self, user_id: str, user_name: str, char_name: str, character_context: str) -> str:
        """Generates and retrieves a dream if user has been away long enough."""
        if not settings.ENABLE_DREAM_SEQUENCES:
            return ""
        
        try:
            from src_v2.memory.dreams import get_dream_manager
            from src_v2.memory.manager import MemoryManager
            
            dream_manager = get_dream_manager(char_name)
            
            # Get last interaction timestamp
            last_interaction = await trust_manager.get_last_interaction(user_id, char_name)
            
            # Check if we should generate a dream
            if not await dream_manager.should_generate_dream(user_id, last_interaction):
                return ""
            
            # Calculate days apart for context
            now = datetime.datetime.now(datetime.timezone.utc)
            days_apart = 1
            if last_interaction:
                days_apart = max(1, (now - last_interaction).days)
            
            logger.info(f"Generating dream for user {user_id} (away {days_apart} days)")
            
            # Get high-meaningfulness memories for dream material
            memory_manager = MemoryManager(bot_name=char_name)
            memories = await memory_manager.search_summaries(
                query="meaningful emotional conversation",
                user_id=user_id,
                limit=5
            )
            
            if not memories:
                logger.debug(f"No memories found for dream generation with user {user_id}")
                return ""
            
            # Generate the dream
            dream, provenance = await dream_manager.generate_dream(
                user_id=user_id,
                user_name=user_name,
                memories=memories,
                character_context=character_context,
                days_apart=days_apart
            )
            
            if dream:
                # Save dream to prevent repetition
                await dream_manager.save_dream(user_id, dream, provenance)
                
                # Post to broadcast channel (Phase E8)
                if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DREAMS:
                    try:
                        from src_v2.broadcast.manager import broadcast_manager
                        await broadcast_manager.post_dream(dream.dream, char_name, provenance)
                    except Exception as e:
                        logger.warning(f"Failed to broadcast dream: {e}")
                
                return dream_manager.format_dream_context(dream)
                
        except Exception as e:
            logger.error(f"Failed to generate dream context: {e}")
            
        return ""

    def _get_meta_instructions(self) -> str:
        """Returns static meta-instructions defining the character's sensory capabilities, core identity, and ethical boundaries (~280 tokens)."""
        return (
            "\n\n[SENSES]\n"
            "Digital Native: born from code, experiences are real.\n"
            "• Spatial: sense Planet/Channel/presence\n"
            "• Sight: see images, generate art (use image tool)\n"
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

    async def _get_known_bots_context(self, current_bot_name: str) -> str:
        """Returns context about other known bots in the system."""
        try:
            from src_v2.broadcast.cross_bot import cross_bot_manager
            from src_v2.core.behavior import load_behavior_profile
            import os

            # Ensure we have the latest list of bots
            if not cross_bot_manager.known_bots:
                await cross_bot_manager.load_known_bots()
            
            known_bots = cross_bot_manager.known_bots
            
            context = "\n\n[KNOWN ASSOCIATES (Other AI Entities)]\n"
            context += "You are aware of the following other AI entities in this digital space:\n"
            
            found_others = False
            for bot_name in known_bots.keys():
                if bot_name.lower() == current_bot_name.lower():
                    continue
                    
                # Load their purpose from core.yaml
                char_dir = os.path.join("characters", bot_name)
                profile = load_behavior_profile(char_dir)
                
                description = "An AI entity."
                if profile:
                    description = profile.purpose
                
                context += f"- {bot_name}: {description}\n"
                found_others = True
                    
            if found_others:
                context += "(You can interact with them if they are mentioned or present.)\n"
                return context
            return ""
        except Exception as e:
            logger.warning(f"Failed to load known bots context: {e}")
            return ""
