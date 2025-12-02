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

import os
import random
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple, Set
from dataclasses import dataclass
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage

from src_v2.config.settings import settings
from src_v2.core.goals import goal_manager, Goal
from src_v2.core.character import CharacterManager
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
    topic: SharedTopic
    initiator: str
    target: str


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
        a_words = set(goal_a.description.lower().split())
        b_words = set(goal_b.description.lower().split())
        
        for theme, keywords in self.TOPIC_KEYWORDS.items():
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
        self.topic_matcher = TopicMatcher()
        self._recent_pairs: Dict[str, datetime] = {}  # "bot1:bot2" -> last_conversation_time
        self._pair_cooldown_minutes = 60  # Don't repeat same pair within 1 hour
    
    async def select_conversation_pair(
        self, 
        available_bots: List[str],
        initiator_name: str
    ) -> Optional[Tuple[str, SharedTopic]]:
        """
        Select a bot to converse with and a topic to discuss.
        Uses weighted random selection from top matches to add variety.
        
        Args:
            available_bots: List of bot names that are online in this guild
            initiator_name: The bot initiating the conversation
            
        Returns:
            Tuple of (target_bot_name, shared_topic) or None
        """
        # Remove self from candidates
        candidates = [b for b in available_bots if b.lower() != initiator_name.lower()]
        
        if not candidates:
            logger.debug(f"No other bots available for {initiator_name} to converse with")
            return None
        
        # Find topic matches with each candidate
        all_matches: List[Tuple[str, SharedTopic]] = []
        
        for candidate in candidates:
            # Check if this pair is on cooldown
            pair_key = self._get_pair_key(initiator_name, candidate)
            if self._is_pair_on_cooldown(pair_key):
                logger.debug(f"Pair {pair_key} on cooldown, skipping")
                continue
                
            topics = self.topic_matcher.find_shared_topics(initiator_name, candidate)
            if topics:
                # Randomly select from top 3 topics for variety
                viable_topics = [t for t in topics[:3] if t.relevance_score > 0.4]
                if viable_topics:
                    selected_topic = random.choice(viable_topics)
                    all_matches.append((candidate, selected_topic))
        
        if not all_matches:
            logger.debug(f"No suitable conversation matches for {initiator_name}")
            return None
        
        # Sort by score and take top 3
        all_matches.sort(key=lambda x: x[1].relevance_score, reverse=True)
        top_matches = all_matches[:3]
        
        # Weighted random selection (higher scores = higher probability)
        weights = [m[1].relevance_score for m in top_matches]
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        selected = random.choices(top_matches, weights=normalized_weights, k=1)[0]
        target_bot, topic = selected
        
        # Record this pair to prevent immediate repetition
        pair_key = self._get_pair_key(initiator_name, target_bot)
        self._recent_pairs[pair_key] = datetime.now(timezone.utc)
        
        logger.info(
            f"Selected conversation pair: {initiator_name} -> {target_bot} "
            f"on topic '{topic.description}' (score: {topic.relevance_score:.2f}, "
            f"selected from {len(top_matches)} candidates)"
        )
        return (target_bot, topic)
    
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
    
    async def generate_opener(
        self,
        initiator_name: str,
        target_name: str,
        topic: SharedTopic
    ) -> Optional[ConversationOpener]:
        """
        Generate an opening message for a bot-to-bot conversation.
        """
        character = self.char_manager.load_character(initiator_name)
        if not character:
            logger.error(f"Could not load character for {initiator_name}")
            return None
        
        # Get character-specific temperature
        temp = character.behavior.temperature if character.behavior else 0.7
        model = character.behavior.model_name if character.behavior else None
        llm = create_llm(mode="main", temperature=temp, model_name=model)
        
        system_prompt = character.system_prompt
        
        prompt = f"""You are starting a casual conversation with another AI character named {target_name} in a public Discord channel.

TOPIC TO DISCUSS: {topic.description}
YOUR GOAL: {topic.initiator_goal.description}
THEIR INTEREST: {topic.responder_goal.description}

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
            
            # Ensure target is mentioned (fallback if LLM forgot)
            if f"@{target_name}" not in content.lower() and target_name.lower() not in content.lower():
                content = f"@{target_name} {content}"
            
            logger.info(f"Generated opener from {initiator_name} to {target_name}: {content}")
            
            return ConversationOpener(
                content=content,
                topic=topic,
                initiator=initiator_name,
                target=target_name
            )
            
        except Exception as e:
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
        
        temp = character.behavior.temperature if character.behavior else 0.7
        model = character.behavior.model_name if character.behavior else None
        llm = create_llm(mode="main", temperature=temp, model_name=model)
        
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
            
        except Exception as e:
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
