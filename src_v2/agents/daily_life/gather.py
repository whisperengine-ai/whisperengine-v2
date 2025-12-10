"""
Gather node - Sense phase of the stigmergic loop.

Queries:
1. Discord API for channel states, mentions, replies
2. Postgres for internal life artifacts (diary, dreams, goals)
3. Neo4j for relationship states (concerning absences)
4. Time context

Uses local embeddings (FastEmbed, $0) for relevance pre-filtering.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import asyncio

import discord
from discord.ext import commands
from loguru import logger

from src_v2.agents.daily_life.state import (
    DailyLifeState,
    InternalLifeState,
    ChannelState,
    ScoredMessage,
    ConcerningAbsence,
    get_time_of_day,
    get_local_time,
)
from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService
from src_v2.core.database import db_manager, require_db
from src_v2.core.goals import GoalManager

# Singleton embedding service for relevance scoring
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

if TYPE_CHECKING:
    from src_v2.core.character import Character


# ──────────────────────────────────────────────────────────────────────────────
# CHARACTER INTERESTS EMBEDDING (cached for relevance checks)
# ──────────────────────────────────────────────────────────────────────────────

_character_interest_cache: Dict[str, List[float]] = {}


async def get_character_interests_embedding(character: "Character") -> List[float]:
    """Get or create embedding of character interests for relevance scoring."""
    
    if character.name in _character_interest_cache:
        return _character_interest_cache[character.name]
    
    # Build interests string from character config
    interests_parts = []
    
    # From behavior profile (core.yaml)
    if character.behavior:
        if character.behavior.drives:
            # drives is a Dict[str, float], we just want the keys (names of drives)
            interests_parts.extend(character.behavior.drives.keys())
        # BehaviorProfile doesn't have "interests" field, but drives cover motivations
    
    # From goals.yaml
    try:
        goal_manager = GoalManager()
        goals = goal_manager.load_goals(character.name)
        for goal in goals:
            interests_parts.append(goal.slug)
            interests_parts.append(goal.description)
    except Exception as e:
        logger.warning(f"[DailyLife] Failed to load goals for {character.name}: {e}")
    
    # Fallback: use character name and purpose
    if not interests_parts:
        interests_parts = [
            character.name,
            getattr(character.behavior, "purpose", "helpful AI assistant") if character.behavior else "helpful AI assistant",
        ]
    
    interests_text = " ".join(filter(None, interests_parts))
    
    # Generate embedding
    embedding_svc = get_embedding_service()
    embedding = await embedding_svc.embed_query_async(interests_text)
    _character_interest_cache[character.name] = embedding
    
    return embedding


# ──────────────────────────────────────────────────────────────────────────────
# RELEVANCE SCORING
# ──────────────────────────────────────────────────────────────────────────────

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import numpy as np
    a_np = np.array(a)
    b_np = np.array(b)
    
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(np.dot(a_np, b_np) / (norm_a * norm_b))


async def score_messages_by_relevance(
    messages: List[discord.Message],
    character: "Character",
    bot_user_id: int,
) -> List[ScoredMessage]:
    """
    Score messages by relevance to character interests using local embeddings.
    
    Cost: $0 (FastEmbed runs locally)
    Latency: ~10ms per message (batched)
    """
    if not messages:
        return []
    
    character_embedding = await get_character_interests_embedding(character)
    
    # Batch embed all message contents
    contents = [m.content for m in messages if m.content]
    if not contents:
        return []
    
    # Use sync embed_documents in executor for batch processing
    embedding_svc = get_embedding_service()
    loop = asyncio.get_running_loop()
    message_embeddings = await loop.run_in_executor(
        None, embedding_svc.embed_documents, contents
    )
    
    scored: List[ScoredMessage] = []
    embed_idx = 0
    
    for msg in messages:
        if not msg.content:
            continue
        
        relevance = cosine_similarity(message_embeddings[embed_idx], character_embedding)
        embed_idx += 1
        
        # Check if this message mentions us
        is_mention = any(m.id == bot_user_id for m in msg.mentions)
        
        # Check if this is a reply to our message
        is_reply_to_me = False
        ref_msg_id = None
        if msg.reference and msg.reference.resolved:
            ref_msg = msg.reference.resolved
            if isinstance(ref_msg, discord.Message) and ref_msg.author.id == bot_user_id:
                is_reply_to_me = True
                ref_msg_id = str(ref_msg.id)
        
        scored.append(ScoredMessage(
            message_id=str(msg.id),
            channel_id=str(msg.channel.id),
            channel_name=getattr(msg.channel, "name", "DM"),
            author_id=str(msg.author.id),
            author_name=msg.author.display_name,
            author_is_bot=msg.author.bot,
            content=msg.content[:500],  # Truncate for context
            created_at=msg.created_at.replace(tzinfo=timezone.utc),
            relevance_score=relevance,
            is_mention=is_mention,
            is_reply_to_me=is_reply_to_me,
            reference_message_id=ref_msg_id,
        ))
    
    return scored


# ──────────────────────────────────────────────────────────────────────────────
# DISCORD STATE GATHERING
# ──────────────────────────────────────────────────────────────────────────────

async def gather_channel_state(
    channel: discord.TextChannel,
    character: "Character",
    bot: commands.Bot,
    limit: int = 50,
) -> ChannelState:
    """Gather state for a single channel."""
    
    now = get_local_time()
    messages: List[discord.Message] = []
    
    try:
        async for msg in channel.history(limit=limit):
            messages.append(msg)
    except discord.Forbidden:
        logger.warning(f"[DailyLife] No permission to read #{channel.name}")
        return ChannelState(
            channel_id=str(channel.id),
            channel_name=channel.name,
            message_count=0,
            last_human_message_age_minutes=float("inf"),
            last_message_age_minutes=float("inf"),
            consecutive_bot_messages=0,
        )
    except Exception as e:
        logger.error(f"[DailyLife] Error reading #{channel.name}: {e}")
        return ChannelState(
            channel_id=str(channel.id),
            channel_name=channel.name,
            message_count=0,
            last_human_message_age_minutes=float("inf"),
            last_message_age_minutes=float("inf"),
            consecutive_bot_messages=0,
        )
    
    if not messages:
        return ChannelState(
            channel_id=str(channel.id),
            channel_name=channel.name,
            message_count=0,
            last_human_message_age_minutes=float("inf"),
            last_message_age_minutes=float("inf"),
            consecutive_bot_messages=0,
        )
    
    # Find last human message
    last_human_msg = next((m for m in messages if not m.author.bot), None)
    if last_human_msg:
        age_minutes = (now - last_human_msg.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
    else:
        age_minutes = float("inf")
    
    # Find last message of any kind (human or bot) - for quiet detection
    last_any_msg = messages[0] if messages else None
    if last_any_msg:
        last_any_age_minutes = (now - last_any_msg.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
    else:
        last_any_age_minutes = float("inf")
    
    # Count consecutive bot messages at top (most recent)
    consecutive_bot = 0
    for msg in messages:
        if msg.author.bot:
            consecutive_bot += 1
        else:
            break
            
    # Optimization: Filter out messages we've already reacted to (Discord-native "seen" check)
    # This prevents processing messages we've already acknowledged, saving Redis calls and LLM tokens
    messages = [m for m in messages if not any(r.me for r in m.reactions)]
    
    # Score messages by relevance
    bot_user_id = bot.user.id if bot.user else 0
    scored_messages = await score_messages_by_relevance(messages, character, bot_user_id)
    
    # Find my last message time to filter relevance trigger
    # We only want to trigger on relevant content that we haven't "addressed" yet.
    # Heuristic: If we spoke AFTER the relevant message, we addressed it (or ignored it intentionally).
    my_id_str = str(bot_user_id)
    my_last_time = None
    
    # messages are usually newest-first from history()
    for msg in messages:
        if str(msg.author.id) == my_id_str:
            my_last_time = msg.created_at.replace(tzinfo=timezone.utc)
            break
    
    # Max relevance score across all human messages
    max_relevance = max((s.relevance_score for s in scored_messages if not s.author_is_bot), default=0.0)
    
    return ChannelState(
        channel_id=str(channel.id),
        channel_name=channel.name,
        message_count=len(messages),
        last_human_message_age_minutes=age_minutes,
        last_message_age_minutes=last_any_age_minutes,
        consecutive_bot_messages=consecutive_bot,
        scored_messages=scored_messages,
        max_relevance_score=max_relevance,
    )


async def gather_mentions(
    channel_states: List[ChannelState],
    bot_user_id: int,
) -> List[ScoredMessage]:
    """Extract UNANSWERED bot mentions from channel states.
    
    IMPORTANT: Only processes mentions from OTHER BOTS.
    Human mentions are handled immediately by the on_message event handler.
    
    A bot mention is considered "answered" if we've directly replied to it.
    Channels at chain limit (too many consecutive bot messages) are skipped.
    """
    
    chain_limit = getattr(settings, "DISCORD_CHECK_CHAIN_LIMIT", 5)
    mentions: List[ScoredMessage] = []
    bot_user_id_str = str(bot_user_id)
    
    logger.debug(f"[DailyLife] gather_mentions: bot_user_id={bot_user_id_str}, processing {len(channel_states)} channels")
    
    for cs in channel_states:
        # Skip channels at chain limit - too many bot messages in a row
        if cs.consecutive_bot_messages >= chain_limit:
            logger.debug(f"[DailyLife] Skipping #{cs.channel_name} - {cs.consecutive_bot_messages} consecutive bot messages (limit: {chain_limit})")
            continue
        
        # Get all messages sorted by time (oldest first)
        all_messages = sorted(cs.scored_messages, key=lambda m: m.created_at)
        
        # Find message IDs WE have directly replied to
        my_replied_to: set[str] = set()
        
        for msg in all_messages:
            if msg.author_id == bot_user_id_str and msg.reference_message_id:
                my_replied_to.add(msg.reference_message_id)
                logger.debug(f"[DailyLife] Found our reply to msg_{msg.reference_message_id}")
        
        logger.debug(
            f"[DailyLife] Channel {cs.channel_id}: "
            f"replied_to={len(my_replied_to)} msgs"
        )
        
        # Collect unanswered bot mentions only
        for msg in all_messages:
            # ONLY process mentions/replies from bots
            # Human mentions are handled by on_message event handler
            if not msg.author_is_bot:
                continue
                
            if not (msg.is_mention or msg.is_reply_to_me):
                continue
                
            # Skip if WE directly replied to this message
            if msg.message_id in my_replied_to:
                logger.debug(f"[DailyLife] Skip msg_{msg.message_id} - already replied by us")
                continue
            
            mentions.append(msg)
            logger.debug(f"[DailyLife] Found unanswered bot mention: msg_{msg.message_id} from {msg.author_name}")
    
    # Sort by creation time (oldest first - FIFO for responses)
    mentions.sort(key=lambda m: m.created_at)
    
    return mentions


def get_watched_channel_ids() -> List[str]:
    """Resolve which channels to watch, with fallbacks."""
    
    channels: List[str] = []
    
    # Priority 1: Explicit watch list
    if hasattr(settings, "DISCORD_CHECK_WATCH_CHANNELS") and settings.DISCORD_CHECK_WATCH_CHANNELS:
        channels.extend(settings.DISCORD_CHECK_WATCH_CHANNELS.split(","))
    
    # Priority 2: Bot conversation channel
    if settings.BOT_CONVERSATION_CHANNEL_ID:
        channels.append(settings.BOT_CONVERSATION_CHANNEL_ID)
    
    # Priority 3: Autonomous posting channel
    if settings.AUTONOMOUS_POSTING_CHANNEL_ID:
        channels.append(settings.AUTONOMOUS_POSTING_CHANNEL_ID)
    
    # Dedupe while preserving order
    seen = set()
    result = []
    for ch in channels:
        ch = ch.strip()
        if ch and ch not in seen:
            seen.add(ch)
            result.append(ch)
    
    return result


# ──────────────────────────────────────────────────────────────────────────────
# INTERNAL STATE GATHERING
# ──────────────────────────────────────────────────────────────────────────────

@require_db("postgres", default_return=InternalLifeState())
async def gather_internal_state(character_name: str) -> InternalLifeState:
    """Query existing artifacts to understand internal life state."""
    
    from src_v2.memory.diary import get_diary_manager
    from src_v2.memory.dreams import get_dream_manager
    
    # Linter safety check (guaranteed by @require_db)
    if not db_manager.postgres_pool:
        return InternalLifeState()

    now = get_local_time()
    state = InternalLifeState()
    time_of_day = get_time_of_day(now.hour)
    
    # Check last diary entry
    no_diary_today = False
    try:
        async with db_manager.postgres_pool.acquire() as conn:
            # Check if diary exists for today (aligns with execute-time check)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            row = await conn.fetchrow(
                """
                SELECT created_at FROM character_artifacts
                WHERE character_name = $1 AND artifact_type = 'diary'
                  AND created_at >= $2
                ORDER BY created_at DESC LIMIT 1
                """,
                character_name,
                today_start,
            )
            if row:
                # Already have a diary for today
                state.last_diary_date = row["created_at"]
                state.diary_overdue = False
            else:
                # No diary for today - check if we've ever written one
                row = await conn.fetchrow(
                    """
                    SELECT created_at FROM character_artifacts
                    WHERE character_name = $1 AND artifact_type = 'diary'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    character_name,
                )
                if row:
                    state.last_diary_date = row["created_at"]
                no_diary_today = True  # Mark for material check below
    except Exception as e:
        logger.error(f"[DailyLife] Error checking diary state: {e}")
    
    # If no diary today AND it's evening, check if we have enough material
    # Diaries should be written in the evening (6pm-10pm) to reflect on the day
    if no_diary_today and time_of_day == "evening":
        try:
            diary_manager = get_diary_manager(character_name)
            richness = await diary_manager.check_material_richness(hours=24)
            min_richness = settings.DIARY_MIN_RICHNESS
            
            if richness >= min_richness:
                state.diary_overdue = True
                logger.debug(f"[DailyLife] Diary material sufficient (richness={richness} >= {min_richness})")
            else:
                state.diary_overdue = False
                logger.info(f"[DailyLife] Diary skipped - insufficient material (richness={richness} < {min_richness})")
        except Exception as e:
            logger.error(f"[DailyLife] Error checking diary material: {e}")
            state.diary_overdue = False  # Don't try if we can't check
    
    # Check last dream
    no_dream_today = False
    try:
        async with db_manager.postgres_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT created_at FROM character_artifacts
                WHERE character_name = $1 AND artifact_type = 'dream'
                ORDER BY created_at DESC LIMIT 1
                """,
                character_name,
            )
            if row:
                state.last_dream_date = row["created_at"]
                # Check if dream was today
                if row["created_at"].date() != now.date():
                    no_dream_today = True
            else:
                no_dream_today = True
    except Exception as e:
        logger.error(f"[DailyLife] Error checking dream state: {e}")
    
    # If it's morning and no dream today, check if we have enough material
    # Dreams should be posted in the morning (6am-12pm) - "waking up and sharing the night's dreams"
    if time_of_day == "morning" and no_dream_today:
        try:
            dream_manager = get_dream_manager(character_name)
            has_material = await dream_manager.check_material_sufficiency(hours=24)
            
            if has_material:
                state.dreams_could_generate = True
                logger.debug(f"[DailyLife] Dream material sufficient")
            else:
                state.dreams_could_generate = False
                logger.info(f"[DailyLife] Dream skipped - insufficient material")
        except Exception as e:
            logger.error(f"[DailyLife] Error checking dream material: {e}")
            state.dreams_could_generate = False
    
    # Check last goal review
    # Goals are only reviewed around GOAL_STRATEGIST_LOCAL_HOUR (default 23:00)
    # No point triggering LLM every 7 minutes just because goals are "stale"
    goal_review_hour = getattr(settings, "GOAL_STRATEGIST_LOCAL_HOUR", 23)
    current_hour = now.hour
    is_goal_review_time = abs(current_hour - goal_review_hour) <= 1  # Within 1 hour of target
    
    try:
        async with db_manager.postgres_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT created_at FROM character_artifacts
                WHERE character_name = $1 AND artifact_type = 'goal_review'
                ORDER BY created_at DESC LIMIT 1
                """,
                character_name,
            )
            if row:
                state.last_goal_review = row["created_at"]
                # Stale if > 7 days AND it's the right time of day
                age_days = (now - row["created_at"].replace(tzinfo=timezone.utc)).total_seconds() / 86400
                state.goals_stale = age_days > 7 and is_goal_review_time
            else:
                # Never reviewed, but only mark stale if it's the right time
                state.goals_stale = is_goal_review_time
    except Exception as e:
        logger.error(f"[DailyLife] Error checking goal state: {e}")
    
    # Check snooze keys (prevent infinite loops if LLM skips internal tasks)
    if db_manager.redis_client:
        try:
            if state.diary_overdue:
                if await db_manager.redis_client.exists(f"daily_life:snooze:diary:{character_name}"):
                    state.diary_overdue = False
                    logger.debug(f"[DailyLife] Diary overdue but snoozed")
            
            if state.dreams_could_generate:
                if await db_manager.redis_client.exists(f"daily_life:snooze:dream:{character_name}"):
                    state.dreams_could_generate = False
                    logger.debug(f"[DailyLife] Dreams due but snoozed")
                    
            if state.goals_stale:
                if await db_manager.redis_client.exists(f"daily_life:snooze:goals:{character_name}"):
                    state.goals_stale = False
                    logger.debug(f"[DailyLife] Goals stale but snoozed")
        except Exception as e:
            logger.warning(f"[DailyLife] Error checking snooze keys: {e}")

    return state


@require_db("neo4j", default_return=[])
async def gather_relationship_state(character_name: str) -> List[ConcerningAbsence]:
    """Query Neo4j for users we're concerned about."""
    
    # Linter safety check (guaranteed by @require_db)
    if not db_manager.neo4j_driver:
        return []

    concerning: List[ConcerningAbsence] = []
    now = get_local_time()
    
    try:
        async with db_manager.neo4j_driver.session() as session:
            # Find users with high trust who haven't been seen recently
            result = await session.run(
                """
                MATCH (c:Character {name: $char_name})-[r:KNOWS]->(u:User)
                WHERE r.trust_score > 0.5 
                  AND r.last_interaction IS NOT NULL
                  AND datetime(r.last_interaction) < datetime() - duration('P3D')
                RETURN u.id AS user_id, 
                       u.name AS user_name, 
                       r.trust_score AS trust,
                       r.last_interaction AS last_seen,
                       r.last_topic AS last_topic
                ORDER BY r.trust_score DESC
                LIMIT 5
                """,
                char_name=character_name,
            )
            
            records = await result.data()
            
            for record in records:
                last_seen = record.get("last_seen")
                if last_seen:
                    if isinstance(last_seen, str):
                        last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                    days_absent = (now - last_seen).days
                else:
                    days_absent = 999
                
                concerning.append(ConcerningAbsence(
                    user_id=record["user_id"],
                    user_name=record.get("user_name", "Unknown"),
                    days_absent=days_absent,
                    relationship_strength=record.get("trust", 0.5),
                    last_topic=record.get("last_topic"),
                ))
    except Exception as e:
        logger.error(f"[DailyLife] Error querying relationship state: {e}")
    
    return concerning


# ──────────────────────────────────────────────────────────────────────────────
# MAIN GATHER FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

async def gather_context(
    state: DailyLifeState,
    bot: commands.Bot,
    character: "Character",
) -> Dict[str, Any]:
    """
    Sense phase: Query Discord + internal state + time context.
    
    Returns dict of state updates. Guaranteed to return a valid dict
    with should_skip set appropriately, never raising exceptions.
    """
    # Default safe return state in case of catastrophic failure
    safe_now = get_local_time()
    safe_return = {
        "current_time": safe_now,
        "time_of_day": get_time_of_day(safe_now.hour),
        "day_of_week": safe_now.strftime("%A"),
        "should_skip": True,
        "has_relevant_content": False,
        "has_pending_internal_tasks": False,
        "mentions": [],
        "channel_states": [],
        "concerning_absences": [],
    }

    try:
        now = safe_now
        time_of_day = safe_return["time_of_day"]
        
        logger.info(f"[DailyLife] {character.name} starting session @ {now.strftime('%H:%M:%S')} ({time_of_day}, {now.strftime('%A')})")
        
        # ── Gather in parallel ──
        channel_ids = get_watched_channel_ids()
        
        # Resolve channel objects
        channels: List[discord.TextChannel] = []
        for ch_id in channel_ids:
            try:
                channel = bot.get_channel(int(ch_id))
                if channel and isinstance(channel, discord.TextChannel):
                    channels.append(channel)
            except ValueError:
                logger.warning(f"[DailyLife] Invalid channel ID: {ch_id}")
        
        # Parallel fetches - use configurable lookback
        message_lookback = getattr(settings, "DISCORD_CHECK_MESSAGE_LOOKBACK", 100)
        channel_tasks = [gather_channel_state(ch, character, bot, limit=message_lookback) for ch in channels]
        internal_task = gather_internal_state(character.name)
        relationship_task = gather_relationship_state(character.name)
        
        results = await asyncio.gather(
            asyncio.gather(*channel_tasks),
            internal_task,
            relationship_task,
            return_exceptions=True,
        )
        
        channel_states: List[ChannelState] = []
        if not isinstance(results[0], Exception):
            channel_states = results[0] # type: ignore
            
        internal_state: InternalLifeState = InternalLifeState()
        if not isinstance(results[1], Exception):
            internal_state = results[1] # type: ignore
            
        concerning_absences: List[ConcerningAbsence] = []
        if not isinstance(results[2], Exception):
            concerning_absences = results[2] # type: ignore
        
        # Extract mentions
        bot_user_id = bot.user.id if bot.user else 0
        mentions = await gather_mentions(channel_states, bot_user_id)
        
        # ── Compute derived flags ──
        relevance_threshold = getattr(settings, "DISCORD_CHECK_RELEVANCE_THRESHOLD", 0.6)
        max_relevance = max((cs.max_relevance_score for cs in channel_states), default=0.0)
        
        has_relevant_content = bool(mentions) or max_relevance >= relevance_threshold
        
        # dreams_could_generate is now set in gather_internal_state (with material check)
        has_pending_internal = (
            internal_state.diary_overdue or 
            internal_state.goals_stale or 
            internal_state.dreams_could_generate or
            bool(concerning_absences)  # Wake up if we miss our friends
        )
        
        # Spontaneity check for quiet times
        # If no relevant content, maybe we just want to say something?
        # Only during waking hours (morning/midday/evening)
        # AND only if channel has been actually quiet (no messages from anyone, including bots)
        is_waking_hours = time_of_day in ["morning", "midday", "evening"]
        wants_to_socialize = False
        
        # Check if any channel has had recent activity (human OR bot)
        # Use minimum post interval as the "quiet" threshold (default 15 mins)
        min_quiet_minutes = getattr(settings, "DISCORD_CHECK_MIN_POST_INTERVAL_MINUTES", 15)
        min_last_message_age = min((cs.last_message_age_minutes for cs in channel_states), default=float("inf"))
        channel_is_quiet = min_last_message_age >= min_quiet_minutes
        
        # Check if another bot recently posted a musing (within 60 mins)
        # This prevents musing storms where multiple bots pile on
        recent_bot_musing = False
        musing_cooldown_minutes = 60
        for cs in channel_states:
            for sm in cs.scored_messages:
                if sm.author_is_bot and "💭 MUSING" in sm.content:
                    # Check age of this musing
                    if hasattr(sm, 'created_at') and sm.created_at:
                        msg_age = (datetime.now(timezone.utc) - sm.created_at).total_seconds() / 60
                        if msg_age < musing_cooldown_minutes:
                            recent_bot_musing = True
                            logger.debug(f"[DailyLife] Recent musing detected ({msg_age:.1f}m ago), suppressing spontaneity")
                            break
            if recent_bot_musing:
                break
        
        if is_waking_hours and not has_relevant_content and not has_pending_internal and channel_is_quiet and not recent_bot_musing:
            # Check if autonomous posting is enabled
            if getattr(settings, "ENABLE_AUTONOMOUS_POSTING", False):
                # Spontaneity chance per check (default 1% every 7 mins -> ~1 post every 11 hours)
                import random
                spontaneity_chance = getattr(settings, "DAILY_LIFE_SPONTANEITY_CHANCE", 0.01)
                if random.random() < spontaneity_chance:
                    wants_to_socialize = True
                    logger.info(f"[DailyLife] Spontaneity trigger! (chance={spontaneity_chance:.0%}, last_msg={min_last_message_age:.1f}m ago) Waking up to socialize.")
        elif is_waking_hours and recent_bot_musing and not has_relevant_content:
            logger.debug(f"[DailyLife] Skipping spontaneity - another bot mused recently (within {musing_cooldown_minutes}m)")
        elif is_waking_hours and not channel_is_quiet and not has_relevant_content:
            logger.debug(f"[DailyLife] Skipping spontaneity - channel active (last msg {min_last_message_age:.1f}m ago < {min_quiet_minutes}m threshold)")

        should_skip = not has_relevant_content and not has_pending_internal and not wants_to_socialize
        
        logger.info(f"[DailyLife] Internal: diary_overdue={internal_state.diary_overdue}, goals_stale={internal_state.goals_stale}, dreams_due={internal_state.dreams_could_generate}, absences={len(concerning_absences)}")
        logger.info(f"[DailyLife] Discord: {len(channel_states)} channels, {len(mentions)} mentions, max_relevance={max_relevance:.2f}, last_msg={min_last_message_age:.1f}m")
        logger.info(f"[DailyLife] Decision: relevant={has_relevant_content}, pending={has_pending_internal}, social={wants_to_socialize} -> should_skip={should_skip}")
        
        if should_skip:
            logger.info(f"[DailyLife] Skipping LLM - nothing relevant, no pending tasks")

        
        return {
            # Time context
            "current_time": now,
            "time_of_day": time_of_day,
            "day_of_week": now.strftime("%A"),
            
            # Internal state
            "diary_overdue": internal_state.diary_overdue,
            "last_diary_date": internal_state.last_diary_date.isoformat() if internal_state.last_diary_date else None,
            "dreams_could_generate": internal_state.dreams_could_generate,
            "goals_stale": internal_state.goals_stale,
            "last_goal_review": internal_state.last_goal_review.isoformat() if internal_state.last_goal_review else None,
            
            # Relationship state
            "concerning_absences": concerning_absences,
            "active_relationship_count": len(concerning_absences),
            
            # Discord state
            "mentions": mentions,
            "channel_states": channel_states,
            
            # Derived flags
            "has_relevant_content": has_relevant_content,
            "has_pending_internal_tasks": has_pending_internal,
            "wants_to_socialize": wants_to_socialize,
            "should_skip": should_skip,
        }
    except Exception as e:
        logger.error(f"[DailyLife] Critical error in gather_context: {e}")
        # Return safe state so graph doesn't crash and LLM isn't called
        return safe_return
