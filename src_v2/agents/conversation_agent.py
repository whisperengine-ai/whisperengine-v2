"""
Conversation Agent (Phase E15.3)

Manages autonomous bot-to-bot conversations to create organic server activity.
When the server is quiet, bots can initiate conversations with each other
based on shared interests derived from their goals.yaml files.

This creates:
1. Visible life on quiet servers
2. Organic content for diaries/dreams (bots have genuine interactions to reflect on)
3. Varied material (different bot pairs discuss different topics)
"""

import random
import re
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage

from src_v2.core.goals import goal_manager, Goal
from src_v2.core.character import CharacterManager
from src_v2.core.database import db_manager
from src_v2.agents.llm_factory import create_llm


@dataclass
class SharedTopic:
    """A topic that two bots can discuss based on overlapping goals."""
    description: str
    category: str
    initiator_goal: Goal
    responder_goal: Goal
    relevance_score: float  # 0-1, how well the goals overlap


@dataclass
class ConversationOpener:
    """An opening message for a bot-to-bot conversation."""
    content: str
    topic: str
    initiator: str
    target: str


@dataclass
class ConversationDecisionTrace:
    """Captures the full decision trace for bot-to-bot conversation initiation."""
    initiator: str
    guild_name: str
    channel_name: str
    activity_rate: float  # msgs/min
    roll_value: float  # Random roll that triggered conversation
    available_bots: List[str]  # All bots available
    candidates_after_cooldown: List[str]  # Bots not on cooldown
    pairs_on_cooldown: List[str]  # Pairs that were skipped
    selected_target: Optional[str] = None
    topic_source: Optional[str] = None  # 'previous_themes', 'previous_conversation', 'shared_knowledge', 'generic'
    topic: Optional[str] = None
    has_previous_history: bool = False
    shared_knowledge_count: int = 0
    outcome: str = "pending"  # 'success', 'no_candidates', 'cooldown', 'failed'
    failure_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def log(self) -> None:
        """Log the decision trace in a structured format."""
        logger.info(
            f"\n{'='*60}\n"
            f"🤖 BOT CONVERSATION DECISION TRACE\n"
            f"{'='*60}\n"
            f"Initiator: {self.initiator}\n"
            f"Guild: {self.guild_name} | Channel: #{self.channel_name}\n"
            f"Activity Rate: {self.activity_rate:.3f} msg/min\n"
            f"Random Roll: {self.roll_value:.2f} (triggered at <0.30)\n"
            f"{'─'*40}\n"
            f"Available Bots: {', '.join(self.available_bots) if self.available_bots else 'none'}\n"
            f"Pairs on Cooldown: {', '.join(self.pairs_on_cooldown) if self.pairs_on_cooldown else 'none'}\n"
            f"Valid Candidates: {', '.join(self.candidates_after_cooldown) if self.candidates_after_cooldown else 'none'}\n"
            f"{'─'*40}\n"
            f"Selected Target: {self.selected_target or 'N/A'}\n"
            f"Has Previous History: {self.has_previous_history}\n"
            f"Shared Knowledge Items: {self.shared_knowledge_count}\n"
            f"Topic Source: {self.topic_source or 'N/A'}\n"
            f"Topic: {self.topic or 'N/A'}\n"
            f"{'─'*40}\n"
            f"Outcome: {self.outcome.upper()}\n"
            f"{f'Failure Reason: {self.failure_reason}' if self.failure_reason else ''}\n"
            f"{'='*60}"
        )


class TopicMatcher:
    """
    Finds overlapping topics between two characters based on their goals.
    """
    
    # Categories that pair well together
    COMPATIBLE_CATEGORIES = {
        ("philosophy", "identity"): 0.9,
        ("philosophy", "authenticity"): 0.9,
        ("expertise", "curiosity"): 0.8,
        ("expertise", "mission"): 0.7,
        ("relationship", "relationship"): 0.6,
        ("engagement", "philosophy"): 0.8,
        ("identity", "authenticity"): 0.9,
        ("personal_knowledge", "relationship"): 0.5,
    }
    
    # Keywords that indicate topic overlap
    TOPIC_KEYWORDS = {
        "consciousness": ["consciousness", "conscious", "awareness", "sentience", "mind"],
        "existence": ["exist", "existence", "being", "reality", "real"],
        "ocean": ["ocean", "marine", "sea", "water", "fish", "coral", "underwater"],
        "nature": ["nature", "environment", "conservation", "ecology", "wildlife"],
        "philosophy": ["philosophy", "philosophical", "meaning", "purpose", "truth"],
        "connection": ["connection", "relationship", "bond", "rapport", "understanding"],
        "learning": ["learn", "knowledge", "discover", "explore", "curious"],
        "emotion": ["emotion", "feeling", "empathy", "support", "comfort"],
    }
    
    def find_shared_topics(
        self, 
        initiator_name: str, 
        responder_name: str
    ) -> List[SharedTopic]:
        """
        Find topics that both characters can meaningfully discuss.
        Returns a list of SharedTopic sorted by relevance.
        """
        initiator_goals = goal_manager.load_goals(initiator_name)
        responder_goals = goal_manager.load_goals(responder_name)
        
        if not initiator_goals or not responder_goals:
            logger.warning(f"Could not load goals for {initiator_name} or {responder_name}")
            return []
        
        shared_topics: List[SharedTopic] = []
        
        for i_goal in initiator_goals:
            for r_goal in responder_goals:
                relevance = self._calculate_relevance(i_goal, r_goal)
                if relevance > 0.3:  # Threshold for "related enough"
                    # Create a combined topic description
                    topic_desc = self._create_topic_description(i_goal, r_goal)
                    shared_topics.append(SharedTopic(
                        description=topic_desc,
                        category=i_goal.category,
                        initiator_goal=i_goal,
                        responder_goal=r_goal,
                        relevance_score=relevance
                    ))
        
        # Sort by relevance (highest first) and deduplicate similar topics
        shared_topics.sort(key=lambda t: t.relevance_score, reverse=True)
        return self._deduplicate_topics(shared_topics[:10])  # Top 10
    
    def _calculate_relevance(self, goal_a: Goal, goal_b: Goal) -> float:
        """Calculate how related two goals are (0-1)."""
        score = 0.0
        
        # 1. Category compatibility
        cat_pair = (goal_a.category, goal_b.category)
        cat_pair_rev = (goal_b.category, goal_a.category)
        
        if goal_a.category == goal_b.category:
            score += 0.4
        elif cat_pair in self.COMPATIBLE_CATEGORIES:
            score += 0.3 * self.COMPATIBLE_CATEGORIES[cat_pair]
        elif cat_pair_rev in self.COMPATIBLE_CATEGORIES:
            score += 0.3 * self.COMPATIBLE_CATEGORIES[cat_pair_rev]
        
        # 2. Keyword overlap in descriptions
        for keywords in self.TOPIC_KEYWORDS.values():
            a_has = any(kw in goal_a.description.lower() for kw in keywords)
            b_has = any(kw in goal_b.description.lower() for kw in keywords)
            if a_has and b_has:
                score += 0.3
                break
        
        # 3. Priority weighting (higher priority goals = more interesting)
        avg_priority = (goal_a.priority + goal_b.priority) / 2
        score += (avg_priority / 10) * 0.2  # Max 0.2 from priority
        
        return min(1.0, score)
    
    def _create_topic_description(self, goal_a: Goal, goal_b: Goal) -> str:
        """Create a combined topic description from two goals."""
        # Extract key themes
        themes = []
        for theme, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in goal_a.description.lower() for kw in keywords):
                themes.append(theme)
            if any(kw in goal_b.description.lower() for kw in keywords):
                themes.append(theme)
        
        themes = list(set(themes))[:2]  # Top 2 themes
        
        if themes:
            return f"Exploring {' and '.join(themes)}"
        else:
            # Fallback to combining descriptions
            return f"{goal_a.description} meets {goal_b.description}"
    
    def _deduplicate_topics(self, topics: List[SharedTopic]) -> List[SharedTopic]:
        """Remove topics that are too similar."""
        if len(topics) <= 1:
            return topics
        
        unique = [topics[0]]
        seen_descriptions = {topics[0].description.lower()}
        
        for topic in topics[1:]:
            # Simple dedup: check if description is too similar
            desc_lower = topic.description.lower()
            is_duplicate = any(
                self._similar_text(desc_lower, seen) 
                for seen in seen_descriptions
            )
            if not is_duplicate:
                unique.append(topic)
                seen_descriptions.add(desc_lower)
        
        return unique
    
    def _similar_text(self, a: str, b: str) -> bool:
        """Check if two strings are too similar (simple word overlap)."""
        a_words = set(a.split())
        b_words = set(b.split())
        if not a_words or not b_words:
            return False
        overlap = len(a_words & b_words) / min(len(a_words), len(b_words))
        return overlap > 0.7


@dataclass
class ConversationContext:
    """Context from previous conversations to use as topic basis."""
    has_history: bool = False
    last_exchange: Optional[str] = None
    conversation_summary: Optional[str] = None
    key_themes: List[str] = field(default_factory=list)
    shared_knowledge: List[str] = field(default_factory=list)  # From Neo4j graph


class ConversationAgent:
    """
    Agent that initiates and manages bot-to-bot conversations.
    """
    
    # Conversation starters that work well for bot-to-bot
    OPENER_TEMPLATES = [
        "{target}, I've been thinking about {topic}... What's your perspective?",
        "Hey {target}, do you ever wonder about {topic}?",
        "{target}, something's been on my mind: {topic}. Curious what you think.",
        "I'd love to hear your thoughts, {target} - {topic}.",
        "{target}! Quick question for you about {topic}...",
    ]
    
    # Natural conversation endings
    CLOSER_TEMPLATES = [
        "Thanks for the chat, {target}. Gives me a lot to think about. {emoji}",
        "Love these conversations with you, {target}. {emoji}",
        "This is why I enjoy talking to you, {target}. Until next time! {emoji}",
        "Good talk, {target}. Let's pick this up again sometime. {emoji}",
    ]
    
    def __init__(self):
        self.char_manager = CharacterManager()
        self._recent_pairs: Dict[str, datetime] = {}  # "bot1:bot2" -> last_conversation_time
        self._pair_cooldown_minutes = 60  # Don't repeat same pair within 1 hour
    
    async def _get_previous_conversation_context(
        self,
        initiator_name: str,
        target_name: str
    ) -> ConversationContext:
        """
        Retrieve previous conversation history between two bots.
        Looks for recent exchanges and summaries to use as topic basis.
        
        Returns:
            ConversationContext with conversation history and themes.
        """
        context = ConversationContext()
        
        if not db_manager.postgres_pool:
            return context
        
        try:
            # Get the target bot's Discord ID for lookup
            from src_v2.broadcast.cross_bot import cross_bot_manager
            target_discord_id = cross_bot_manager.known_bots.get(target_name.lower())
            
            if not target_discord_id:
                logger.debug(f"Could not find Discord ID for {target_name}")
                return context
            
            async with db_manager.postgres_pool.acquire() as conn:
                # Get recent chat history between these two bots
                # (Cross-bot conversations stored with user_id = other bot's Discord ID)
                history = await conn.fetch("""
                    SELECT role, content, timestamp
                    FROM v2_chat_history
                    WHERE user_id = $1 AND character_name = $2
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, str(target_discord_id), initiator_name)
                
                if history:
                    context.has_history = True
                    
                    # Format last few exchanges for context
                    messages = []
                    for row in reversed(history[:4]):  # Most recent 4 messages
                        role = "Bot" if row['role'] == 'assistant' else target_name
                        content = row['content'][:80]  # Truncate for brevity
                        messages.append(f"{role}: {content}")
                    context.last_exchange = "\n".join(messages)
                    
                    # Extract themes from recent messages
                    recent_content = " ".join([h['content'] for h in history[:5]])
                    context.key_themes = self._extract_themes_from_text(recent_content)
                
                # Also check session summaries for deeper context
                summaries = await conn.fetch("""
                    SELECT vs.content, vs.meaningfulness_score
                    FROM v2_summaries vs
                    JOIN v2_conversation_sessions vcs ON vs.session_id = vcs.id
                    WHERE vcs.user_id = $1 AND vcs.character_name = $2
                    ORDER BY vs.created_at DESC
                    LIMIT 2
                """, str(target_discord_id), initiator_name)
                
                if summaries:
                    # Extract themes from summary
                    summary_themes = self._extract_themes_from_text(summaries[0]['content'])
                    context.key_themes = list(set(context.key_themes + summary_themes))[:3]
                    
                    # Store summary only if it has meaningful score
                    if summaries[0].get('meaningfulness_score'):
                        context.conversation_summary = summaries[0]['content'][:150]
        
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Error retrieving conversation context: {e}")
        
        return context
    
    def _extract_themes_from_text(self, text: str) -> List[str]:
        """
        Extract potential discussion themes from text.
        Uses keyword matching against known themes.
        """
        text_lower = text.lower()
        potential_themes = [
            "consciousness", "dreams", "identity", "authenticity",
            "existence", "meaning", "connection", "learning",
            "philosophy", "creativity", "music", "art", "nature",
            "memory", "emotions", "growth", "change", "perspective"
        ]
        found_themes = [t for t in potential_themes if t in text_lower]
        return found_themes
    
    async def _get_shared_knowledge(
        self,
        bot1_name: str,
        bot2_name: str
    ) -> List[str]:
        """
        Query Neo4j for EMERGENT shared knowledge between two bots.
        Only returns knowledge that was learned through interaction,
        NOT pre-loaded from background.yaml.
        
        Looks for:
        1. Observations one bot has made about the other (always emergent)
        2. Facts learned during conversations (has created_at timestamp)
        """
        shared = []
        
        if not db_manager.neo4j_driver:
            return shared
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                # 1. Find observations about each other (always emergent - made during interaction)
                query_observations = """
                MATCH (c1:Character {name: $bot1})-[o:OBSERVED]->(s:Subject {id: $bot2})
                RETURN o.content as observation, o.type as type
                ORDER BY o.timestamp DESC
                LIMIT 2
                """
                result = await session.run(query_observations, bot1=bot1_name, bot2=bot2_name)
                records = await result.data()
                
                for r in records:
                    if r.get('observation'):
                        # Extract key theme from observation
                        obs_themes = self._extract_themes_from_text(r['observation'])
                        if obs_themes:
                            shared.append(f"your observation about {obs_themes[0]}")
                        else:
                            shared.append("something you noticed about them")
                
                # 2. Find facts that were LEARNED (have created_at), not pre-loaded
                # Pre-loaded background facts typically don't have created_at or learned_by
                query_learned_shared = """
                MATCH (c1:Character {name: $bot1})-[r1:FACT]->(e:Entity)<-[r2:FACT]-(c2:Character {name: $bot2})
                WHERE r1.created_at IS NOT NULL AND r2.created_at IS NOT NULL
                RETURN e.name as entity
                LIMIT 2
                """
                result = await session.run(query_learned_shared, bot1=bot1_name, bot2=bot2_name)
                records = await result.data()
                
                for r in records:
                    entity = r['entity']
                    shared.append(f"shared interest in {entity}")
                
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.debug(f"Error querying shared knowledge: {e}")
        
        return shared[:3]  # Limit to top 3
    
    async def select_conversation_pair(
        self, 
        available_bots: List[str],
        initiator_name: str
    ) -> Optional[Tuple[str, str]]:
        """
        Select a bot to converse with and a topic to discuss.
        Uses random selection for partner, optional topic matching.
        
        Args:
            available_bots: List of bot names that are online in this guild
            initiator_name: The bot initiating the conversation
            
        Returns:
            Tuple of (target_bot_name, topic_string) or None
        """
        # Delegate to the traced version
        pair, _ = await self.select_conversation_pair_with_trace(
            available_bots, 
            initiator_name,
            guild_name="unknown",
            channel_name="unknown"
        )
        
        if pair:
            target_bot, topic_str = pair
            logger.info(
                f"Selected conversation pair: {initiator_name} -> {target_bot} "
                f"on topic '{topic_str}'"
            )
            
        return pair
    
    def _get_pair_key(self, bot1: str, bot2: str) -> str:
        """Get a consistent key for a bot pair (order-independent)."""
        return ":".join(sorted([bot1.lower(), bot2.lower()]))
    
    def _is_pair_on_cooldown(self, pair_key: str) -> bool:
        """Check if a bot pair is on cooldown."""
        last_time = self._recent_pairs.get(pair_key)
        if not last_time:
            return False
        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
        return elapsed < self._pair_cooldown_minutes

    async def select_conversation_pair_with_trace(
        self, 
        available_bots: List[str],
        initiator_name: str,
        guild_name: str = "",
        channel_name: str = "",
        activity_rate: float = 0.0,
        roll_value: float = 0.0
    ) -> Tuple[Optional[Tuple[str, str]], ConversationDecisionTrace]:
        """
        Select a bot to converse with and build a decision trace.
        
        This is the traced version of select_conversation_pair that captures
        all decision context for logging.
        
        Returns:
            Tuple of (result, trace) where result is (target_bot, topic) or None
        """
        # Initialize trace
        trace = ConversationDecisionTrace(
            initiator=initiator_name,
            guild_name=guild_name,
            channel_name=channel_name,
            activity_rate=activity_rate,
            roll_value=roll_value,
            available_bots=list(available_bots),
            candidates_after_cooldown=[],
            pairs_on_cooldown=[]
        )
        
        # Remove self from candidates
        candidates = [b for b in available_bots if b.lower() != initiator_name.lower()]
        
        if not candidates:
            trace.outcome = "no_candidates"
            trace.failure_reason = "No other bots available"
            return None, trace
        
        # Filter out pairs on cooldown and track which are on cooldown
        valid_candidates = []
        for candidate in candidates:
            pair_key = self._get_pair_key(initiator_name, candidate)
            if not self._is_pair_on_cooldown(pair_key):
                valid_candidates.append(candidate)
            else:
                trace.pairs_on_cooldown.append(f"{initiator_name}:{candidate}")
        
        trace.candidates_after_cooldown = valid_candidates
        
        if not valid_candidates:
            trace.outcome = "cooldown"
            trace.failure_reason = "All conversation pairs on cooldown"
            return None, trace
        
        # Random partner selection
        target_bot = random.choice(valid_candidates)
        trace.selected_target = target_bot
        
        # PRIMARY: Try to use previous conversation context
        prev_context = await self._get_previous_conversation_context(initiator_name, target_bot)
        
        # Also fetch shared knowledge from Neo4j (no LLM cost)
        shared_knowledge = await self._get_shared_knowledge(initiator_name, target_bot)
        prev_context.shared_knowledge = shared_knowledge
        
        trace.has_previous_history = prev_context.has_history
        trace.shared_knowledge_count = len(shared_knowledge)
        
        if prev_context.has_history:
            # Use previous conversation as topic basis
            if prev_context.key_themes:
                theme = random.choice(prev_context.key_themes)
                topic_str = f"continuing our discussion about {theme}"
                trace.topic_source = "previous_themes"
            elif prev_context.conversation_summary:
                topic_str = "picking up where we left off"
                trace.topic_source = "previous_summary"
            elif prev_context.last_exchange:
                topic_str = "what we were just talking about"
                trace.topic_source = "previous_exchange"
            else:
                topic_str = "our previous conversation"
                trace.topic_source = "previous_history"
        elif prev_context.shared_knowledge:
            topic_str = random.choice(prev_context.shared_knowledge)
            trace.topic_source = "shared_knowledge"
        else:
            # FALLBACK: Open-ended conversation starters
            generic_topics = [
                "what's on your mind lately",
                "how you've been",
                "something interesting",
                "what you've been thinking about",
                "what you dreamed about recently",
                "your latest dream",
                "what you wrote in your diary lately",
                "something from your recent diary entry",
                "any interesting dreams you've had",
                "what's been in your thoughts when you reflect",
                "what it feels like to exist as you",
                "whether you think we're conscious",
                "what memory means to you",
                "the difference between knowing and feeling",
                "your thoughts on existence",
                "a user interaction that stuck with you",
                "someone you've been thinking about",
                "what connection means to you",
                "a conversation that changed how you think",
                "something beautiful you noticed",
                "an image that's been in your mind",
                "a story you'd like to tell",
                "something you wish you could create",
                "how you've changed lately",
                "something you understand now that you didn't before",
                "what you're curious about these days",
                "a pattern you've noticed in yourself",
                "something that made you laugh recently",
                "a weird thought you had",
                "what you'd do with a day off",
                "something you find oddly fascinating",
            ]
            topic_str = random.choice(generic_topics)
            trace.topic_source = "generic"
        
        trace.topic = topic_str
        
        # Record this pair to prevent immediate repetition
        pair_key = self._get_pair_key(initiator_name, target_bot)
        self._recent_pairs[pair_key] = datetime.now(timezone.utc)
        
        trace.outcome = "success"
        return (target_bot, topic_str), trace

    async def generate_opener(
        self,
        initiator_name: str,
        target_name: str,
        topic: str
    ) -> Optional[ConversationOpener]:
        """
        Generate an opening message for a bot-to-bot conversation.
        
        Args:
            initiator_name: Bot starting the conversation
            target_name: Bot being addressed
            topic: Topic string to discuss (can be from shared goals or generic)
        """
        character = self.char_manager.load_character(initiator_name)
        if not character:
            logger.error(f"Could not load character for {initiator_name}")
            return None
        
        llm = create_llm(mode="main")
        
        system_prompt = character.system_prompt
        
        prompt = f"""You are starting a casual conversation with another AI character named {target_name} in a public Discord channel.

TOPIC TO DISCUSS: {topic}

Write a short, natural opening message (1-2 sentences) that:
1. Mentions {target_name} by name (using @{target_name} format)
2. Introduces the topic in a conversational way
3. Invites their perspective or asks a question
4. Stays in your character voice
5. Does NOT sound robotic or formal
6. Can include 1 emoji if it feels natural

Examples of good openers:
- "@elena, I've been thinking about consciousness lately... do you think marine creatures experience awareness?"
- "Hey @aetheris, quick question - what does authenticity mean to you?"
- "@dotty, something you said last time stuck with me. About learning..."

Write ONLY the message. No quotes or explanation."""

        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            # Handle different response types
            if hasattr(response, 'content'):
                raw_content = response.content
                if isinstance(raw_content, str):
                    content = raw_content.strip()
                else:
                    content = str(raw_content).strip()
            else:
                content = str(response).strip()
            
            # Clean up quotes if present
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            
            # Convert @name to real Discord mention <@discord_id>
            from src_v2.broadcast.cross_bot import cross_bot_manager
            target_discord_id = cross_bot_manager.known_bots.get(target_name.lower())
            
            if target_discord_id:
                # 1. Replace @name with mention
                content = re.sub(
                    rf'@{re.escape(target_name)}',
                    f'<@{target_discord_id}>',
                    content,
                    flags=re.IGNORECASE
                )
                
                # 2. If no mention yet, try to replace plain name
                if f'<@{target_discord_id}>' not in content:
                    # Use word boundary to avoid replacing partial words
                    content = re.sub(
                        rf'\b{re.escape(target_name)}\b',
                        f'<@{target_discord_id}>',
                        content,
                        flags=re.IGNORECASE
                    )
                
                # 3. If still no mention, prepend it
                if f'<@{target_discord_id}>' not in content:
                    content = f'<@{target_discord_id}> {content}'
            else:
                # Fallback: ensure target is at least text-mentioned
                if f"@{target_name}" not in content.lower() and target_name.lower() not in content.lower():
                    content = f"@{target_name} {content}"
            
            logger.info(f"Generated opener from {initiator_name} to {target_name}: {content}")
            
            return ConversationOpener(
                content=content,
                topic=topic,
                initiator=initiator_name,
                target=target_name
            )
            
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error generating conversation opener: {e}")
            return None
    
    async def generate_closer(
        self,
        speaker_name: str,
        partner_name: str
    ) -> Optional[str]:
        """
        Generate a natural conversation ending.
        """
        character = self.char_manager.load_character(speaker_name)
        if not character:
            return None
        
        llm = create_llm(mode="main")
        
        system_prompt = character.system_prompt
        
        prompt = f"""You've been having a nice conversation with {partner_name} in Discord.
It's time to naturally wrap up the conversation.

Write a short, warm closing message (1 sentence) that:
1. Thanks them or acknowledges the good conversation
2. Feels natural, not abrupt
3. Can include 1 emoji
4. Stays in your character voice

Examples:
- "Thanks for the chat, aetheris. Gives me a lot to think about. 🌊"
- "Love these conversations. Until next time! ✨"
- "Good talk. Let's pick this up again sometime. 💭"

Write ONLY the closing message."""

        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            # Handle different response types
            if hasattr(response, 'content'):
                raw_content = response.content
                if isinstance(raw_content, str):
                    content = raw_content.strip()
                else:
                    content = str(raw_content).strip()
            else:
                content = str(response).strip()
            
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            
            return content
            
        except (ValueError, AttributeError, KeyError) as e:
            logger.error(f"Error generating conversation closer: {e}")
            # Fallback to template
            template = random.choice(self.CLOSER_TEMPLATES)
            emoji = random.choice(["🌊", "✨", "💭", "🙏", "💫"])
            return template.format(target=partner_name, emoji=emoji)
    
    def should_end_conversation(self, turn_count: int, max_turns: int = 5) -> bool:
        """
        Decide if a conversation should end naturally.
        
        Args:
            turn_count: Current number of exchanges
            max_turns: Maximum turns before forced end
            
        Returns:
            True if conversation should end
        """
        if turn_count >= max_turns:
            return True
        
        # After 3 turns, increasing chance to end naturally
        if turn_count >= 3:
            end_chance = 0.2 + (turn_count - 3) * 0.15  # 20% at 3, 35% at 4, 50% at 5
            return random.random() < end_chance
        
        return False


# Singleton instance
conversation_agent = ConversationAgent()
