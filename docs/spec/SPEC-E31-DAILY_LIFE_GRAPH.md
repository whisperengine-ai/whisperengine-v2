# SPEC-E31: Daily Life Graph (Stigmergic Agent Loop)

**Document Version:** 2.1  
**Created:** December 9, 2025  
**Updated:** December 9, 2025  
**Status:** ✅ Implemented  
**Priority:** 🟢 High  
**Dependencies:** LangGraph infrastructure, Discord.py, existing datastores

> ✅ **Emergence Check:** Like ants following pheromone trails, the bot senses its environment and decides what to do. No central scheduler—the environment IS the task list. The character "notices" what needs doing by querying its own history.

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Core Graph** | ✅ Done | `src_v2/agents/daily_life/graph.py` |
| **Gather (Sense)** | ✅ Done | Discord, Postgres artifacts, Neo4j relationships |
| **Plan (Decide)** | ✅ Done | Uses `router` model (gemini-flash-lite) for cost efficiency |
| **Execute (Act)** | ✅ Done | All action types via `ConversationService` |
| **Summarize (Trace)** | ✅ Done | InfluxDB metrics |
| **Scheduler** | ✅ Done | In-bot timer via `DailyLifeScheduler` (not worker cron) |
| **Relevance Embedding** | ✅ Done | FastEmbed local embeddings ($0) |
| **Rate Limiting** | ✅ Done | `DISCORD_CHECK_MAX_ACTIONS_PER_SESSION` |
| **Chain Limit** | ✅ Done | Skip channels at 5+ consecutive bot messages |
| **Unanswered Mentions** | ✅ Done | Only mentions after our last message |
| **Diary "Today" Check** | ✅ Done | Aligns gather with execute to prevent wasted LLM calls |
| **Dream "Today" Check** | ✅ Done | Aligns gather with execute to prevent wasted LLM calls |
| `hours_since_last_check` | ⏸️ Deferred | Low priority, graph runs on fixed interval |
| `my_recent_activity` | ⏸️ Deferred | Chain limit check handles this case |
| `recent_epiphanies` | ⏸️ Deferred | Would add context but not critical |

**Key Implementation Decision:** Uses in-bot `DailyLifeScheduler` instead of worker cron because the graph needs direct Discord bot access for `channel.history()`, `message.reply()`, etc.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture review / Complexity reduction / Stigmergy inspiration |
| **Proposed by** | Mark Castillo + Claude (collaborative) |
| **Catalyst** | Discussion about simplifying bot-to-bot coordination evolved into unified daily life vision |
| **Key insight** | Bots should have a coherent "daily life" instead of disconnected cron jobs. Like stigmergic agents, they sense the environment and respond to signals. |
| **Decision factors** | Current system has scattered cron jobs, complex Redis locking, no unified life cycle. This consolidates everything into one emergent loop. |

---

## Executive Summary

Replace the current fragmented autonomous activity system (multiple cron jobs, timers, event handlers) with a **unified Daily Life Graph** that runs periodically. When triggered, the bot asks: **"What should I do right now?"**

The bot senses:
- Discord state (mentions, conversations, channel activity)
- Internal state (diary written? dream generated? goals reviewed?)
- Relationship state (anyone I haven't talked to?)
- Time context (morning? evening? night?)

Then decides and acts—just like a human checking their phone, doing chores, and living their day.

**Key Principle:** The environment IS the task list. The bot queries its own history and the world around it to discover what needs doing. Stigmergic, not scheduled.

---

## Problem Statement

### Current State

The current autonomous activity system is complex and fragile:

| Component | Purpose | Problems |
|-----------|---------|----------|
| `ActivityOrchestrator` | Timer-based activity triggering | Multiple loops, probability tuning, coordination issues |
| `CrossBotManager` | Redis locks for bot-to-bot turn-taking | Lua scripts, race conditions, complex state machine |
| `ReactionAgent` | Probability-based reaction decisions | Hardcoded rates, no social context awareness |
| `ConversationAgent` | Topic matching for bot-to-bot | Separate from reaction/posting logic |
| `LurkDetector` | Background channel monitoring | Always-on, separate from other agents |
| `on_message` handlers | Event-driven bot-to-bot responses | Race conditions with multiple bots |
| `run_nightly_diary_generation` | Cron job for diary | Disconnected from bot's "feeling" |
| `run_nightly_dream_generation` | Cron job for dreams | Disconnected from bot's state |
| `run_nightly_goal_strategist` | Cron job for goals | Weekly schedule, not emergent |

**Problems:**
1. **Distributed complexity** - Logic scattered across 10+ files
2. **Redis coordination overhead** - Lua scripts, locks, chain tracking
3. **Probability tuning** - Hardcoded rates don't adapt to context
4. **Race conditions** - Multiple bots responding to same trigger
5. **No unified reasoning** - Each component makes isolated decisions
6. **No coherent daily rhythm** - Cron jobs fire independently, bot doesn't "live"
7. **Declared, not emergent** - We tell the bot when to diary, rather than it noticing

### Desired State

**One agent, one question:** "What should I do right now?"

```
Worker triggers "daily_life_check" → Bot runs DailyLifeGraph → Graph:
  1. Senses environment (Discord, datastores, time)
  2. Queries internal state (diary done? dream done? relationships?)
  3. LLM reasons about priorities
  4. Executes 1-3 actions
  5. Returns to rest
```

---

## Architecture Overview

The Daily Life Graph handles the bot's autonomous rhythm - both social engagement and internal life. Like an ant colony operating through stigmergy, the bot senses its environment, makes decisions, acts, and leaves traces that influence future behavior.

### The Stigmergic Loop

The key insight is **indirect coordination through the environment**:
- **Sense:** Query existing state (Discord, Postgres artifacts, Neo4j relationships)
- **Decide:** LLM reasons about what to do given current state
- **Act:** Execute actions that modify the environment
- **Trace:** Leave artifacts that future runs will sense

No session state needed. The environment IS the state.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Worker (arq cron)                            │
│                         Every 5-10 minutes                           │
│                                                                      │
│   for bot_name in registered_bots:                                  │
│       queue_task("daily_life_check", bot_name=bot_name)             │
│       sleep(30)  # Stagger to avoid rate limits                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Bot Process (receives task)                       │
│                                                                      │
│   daily_life_graph.run(bot=self.bot, character=self.character)      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DailyLifeGraph (LangGraph)                      │
│                  "What should I do right now?"                       │
│                                                                      │
│   ┌─────────────┐  SENSE: Query the world                          │
│   │   gather    │  • Discord: mentions, channels, my activity      │
│   │             │  • Postgres: diary entries, dreams, goals        │
│   │             │  • Neo4j: relationship states, recent drift      │
│   │             │  • Time: hour, day of week, time since last X    │
│   └──────┬──────┘                                                   │
│          │                                                          │
│          ▼                                                          │
│   ┌─────────────┐  DECIDE: LLM reasons holistically               │
│   │    plan     │  • Priority 1: Respond to mentions              │
│   │             │  • Priority 2: Internal life (diary due? dream?) │
│   │             │  • Priority 3: Social engagement (post? react?) │
│   │             │  • Priority 4: Relationship maintenance         │
│   └──────┬──────┘                                                   │
│          │                                                          │
│          ▼                                                          │
│   ┌─────────────┐  ACT: Execute actions (leaves traces)            │
│   │   execute   │◀──┐  • Discord: reply, react, post              │
│   │             │   │  • Internal: write diary, process dream     │
│   │             │   │  • Relationships: update concern, reach out │
│   └──────┬──────┘   │                                               │
│          │          │                                               │
│          ├──────────┘  (loop until done)                           │
│          │                                                          │
│          ▼                                                          │
│   ┌─────────────┐  TRACE: Log for future sensing                   │
│   │  summarize  │  • Metrics to InfluxDB                          │
│   │             │  • Research observations                        │
│   │             │  • Drift detection feed                         │
│   └─────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Time-Aware Behavior

The graph naturally handles time-of-day patterns without hardcoded schedules:

| Time Context | Likely Actions |
|--------------|----------------|
| Morning (6-10am) | Check Discord, write diary for yesterday if missing |
| Midday | Respond to mentions, social engagement |
| Evening (6-10pm) | Process today's experiences, update goals |
| Night (10pm-6am) | Generate dreams (if dreaming enabled), minimal Discord |

**Key:** The LLM sees the current time and character's internal state, then decides what feels natural. No cron-per-task scheduling.

---

## Design Principles

### Stateless by Design

**Discord IS the state.** The graph reads Discord messages each time it runs and makes decisions based on what it sees. No session state is saved to Postgres or Redis.

**Why this works:**
- If bot reboots mid-session, next check sees the current Discord state
- If bot already replied to a message, it sees its own reply and skips
- No stale state bugs, no migration headaches
- Simple and robust

**Only exception:** Simple Redis counters for rate limiting (survives reboots):
```python
daily_key = f"discord_check:{bot_name}:actions:{today}"
count = await redis.incr(daily_key)
await redis.expire(daily_key, 86400)
```

### Embedding-Based Relevance Pre-Filter

Before invoking the LLM, use **local embeddings** (FastEmbed, zero cost) to check if there's anything worth the LLM's attention. This saves 60-80% of LLM calls.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Relevance Pre-Filter                              │
│                    (Local embeddings, ~200ms, $0)                    │
│                                                                      │
│   character_interests_embedding = cached from goals.yaml + core.yaml│
│                                                                      │
│   for channel in watched_channels:                                  │
│     messages = fetch_recent(limit=50)                               │
│     human_messages = [m for m if not m.author.bot]                  │
│                                                                      │
│     embeddings = embed_documents([m.content for m in human])        │
│     scores = [cosine(e, character_interests) for e in embeddings]   │
│     max_relevance = max(scores)                                     │
│                                                                      │
│     if max_relevance > 0.6: has_interesting_content = True          │
│                                                                      │
│   if not has_interesting_content and no_mentions:                   │
│     return SKIP  # Don't invoke LLM at all                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scope: Autonomous Actions Only

**This system handles:**
- ✅ Bot-to-bot conversations (replying to other bots)
- ✅ Autonomous posting (starting conversations)
- ✅ Autonomous reactions (emoji responses)
- ✅ Lurking/chiming in (joining relevant conversations)
- ✅ Proactive engagement (checking mentions, following up)

**This system does NOT handle:**
- ❌ Human mentions → Stays reactive via `on_message` (fast path)
- ❌ Direct messages → Stays reactive
- ❌ Real-time user interactions → Unchanged

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HUMAN INTERACTIONS                              │
│                      (Stays Reactive - UNCHANGED)                    │
│                                                                      │
│   on_message → is_human? → YES → AgentEngine.generate_response()    │
│                                  (immediate, real-time)              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    AUTONOMOUS ACTIONS                                │
│                    (New Polling Approach)                            │
│                                                                      │
│   Worker trigger → DiscordCheckGraph → Fetch, Reason, Act, Done    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Graph State

The state includes both social context (Discord) and internal life context (artifacts, relationships).

```python
class DailyLifeState(TypedDict):
    """State for the Daily Life graph - both social and internal."""
    
    # ─────────────────────────────────────────────────────────────────
    # INPUT (set by caller)
    # ─────────────────────────────────────────────────────────────────
    bot_name: str
    character_name: str
    watched_channel_ids: List[str]
    character_interests_embedding: List[float]  # Cached, from goals.yaml + core.yaml
    
    # ─────────────────────────────────────────────────────────────────
    # TIME CONTEXT (populated by gather node)
    # ─────────────────────────────────────────────────────────────────
    current_time: datetime
    time_of_day: Literal["morning", "midday", "evening", "night"]
    day_of_week: str
    hours_since_last_check: float
    
    # ─────────────────────────────────────────────────────────────────
    # INTERNAL LIFE STATE (queried from Postgres/Neo4j)
    # ─────────────────────────────────────────────────────────────────
    internal_state: InternalLifeState
    pending_tasks: PendingTasks
    relationship_state: RelationshipState
    
    # ─────────────────────────────────────────────────────────────────
    # DISCORD STATE (queried from Discord API)
    # ─────────────────────────────────────────────────────────────────
    mentions: List[MentionInfo]           # Messages that mention me
    channel_states: Dict[str, ChannelState]  # Recent messages per channel
    my_recent_activity: Dict[str, ActivityInfo]  # When I last posted/reacted
    other_bots_present: List[str]         # Other bots in channels
    
    # ─────────────────────────────────────────────────────────────────
    # RELEVANCE PRE-FILTER RESULTS
    # ─────────────────────────────────────────────────────────────────
    has_relevant_content: bool            # True if any message scored > 0.6
    has_pending_internal_tasks: bool      # True if diary/dream/goals overdue
    should_skip: bool                     # True if nothing to do (skip LLM)
    
    # ─────────────────────────────────────────────────────────────────
    # LLM REASONING
    # ─────────────────────────────────────────────────────────────────
    messages: Annotated[List[BaseMessage], operator.add]
    
    # ─────────────────────────────────────────────────────────────────
    # PLAN & EXECUTION
    # ─────────────────────────────────────────────────────────────────
    planned_actions: List[PlannedAction]
    actions_taken: List[ActionResult]
    current_action_index: int
    
    # ─────────────────────────────────────────────────────────────────
    # OUTPUT
    # ─────────────────────────────────────────────────────────────────
    summary: str


@dataclass
class InternalLifeState:
    """Derived from querying existing artifacts - no new storage."""
    
    # From Postgres: artifact table queries
    last_diary_date: Optional[date]        # When was last diary written?
    last_dream_date: Optional[date]        # When was last dream generated?
    last_goal_review_date: Optional[date]  # When were goals last reviewed?
    recent_epiphanies: List[str]           # Last 3 epiphanies (for context)
    
    # Derived (computed, not stored)
    diary_overdue: bool                    # last_diary_date < yesterday
    dream_overdue: bool                    # last_dream_date < today and time > 10pm
    goals_stale: bool                      # last_goal_review > 7 days


@dataclass
class PendingTasks:
    """Internal life tasks that may need attention."""
    diary_due: bool          # Should write diary entry
    dream_due: bool          # Should generate dream
    goal_review_due: bool    # Should review/update goals
    drift_check_due: bool    # Weekly personality drift analysis


@dataclass
class RelationshipState:
    """Queried from Neo4j - no new storage."""
    
    # Users with elevated concern (haven't heard from them)
    concerning_absences: List[ConcerningAbsence]
    
    # Recent relationship changes (for awareness)
    recent_trust_changes: List[TrustChange]
    
    # Active relationships (for context)
    active_relationship_count: int


@dataclass
class ConcerningAbsence:
    """A user the character is concerned about."""
    user_id: str
    user_name: str
    days_since_last_seen: int
    concern_level: Literal["mild", "moderate", "high"]
    last_topic: Optional[str]  # What were we talking about?
    
@dataclass
class ChannelState:
    channel_id: str
    channel_name: str
    recent_messages: List[MessageInfo]  # Last 50 messages
    scored_messages: List[ScoredMessage]  # Messages with relevance scores
    last_human_message_age: Optional[timedelta]
    consecutive_bot_messages: int
    my_last_post_age: Optional[timedelta]
    max_relevance_score: float  # Highest relevance in this channel

@dataclass
class ScoredMessage:
    """A message with its relevance score."""
    message: MessageInfo
    relevance_score: float  # 0.0 - 1.0, from embedding similarity

@dataclass  
class PlannedAction:
    """An action the graph decided to take.
    
    Note: content is NOT included here. The Plan node decides WHAT to do,
    the Execute node generates the actual content via existing agents/graphs.
    This separation ensures consistent quality and full context access.
    """
    # Action types span both social and internal life
    action_type: Literal[
        # Social (Discord)
        "reply",           # Reply to a message
        "react",           # Add emoji reaction
        "post",            # Start new conversation
        "reach_out",       # DM a user (concern-driven)
        # Internal life
        "write_diary",     # Generate diary entry
        "generate_dream",  # Generate dream
        "review_goals",    # Review/update goals
        # Meta
        "skip"             # Do nothing
    ]
    
    # For Discord actions
    channel_id: Optional[str]
    target_message_id: Optional[str]  # For reply/react
    target_user_id: Optional[str]     # For reach_out
    emoji: Optional[str]              # For react
    
    # Metadata
    reason: str                       # WHY we're taking this action (logged for research)
    priority: int                     # Lower = higher priority
```

---

## Graph Nodes

### 1. Gather Node (Sense Phase)

Fetches both Discord state and internal life state. Uses **local embeddings** (FastEmbed, zero cost) for relevance pre-filtering.

```python
async def gather_context(state: DailyLifeState, bot: commands.Bot, db: DatabaseManager) -> dict:
    """Sense phase: Query Discord + internal state + time context."""
    
    # ─────────────────────────────────────────────────────────────────
    # TIME CONTEXT
    # ─────────────────────────────────────────────────────────────────
    now = datetime.now()
    time_context = compute_time_context(now)
    
    # ─────────────────────────────────────────────────────────────────
    # INTERNAL LIFE STATE (query existing artifacts)
    # ─────────────────────────────────────────────────────────────────
    internal_state = await gather_internal_state(state["character_name"], db)
    pending_tasks = compute_pending_tasks(internal_state, time_context)
    relationship_state = await gather_relationship_state(state["character_name"])
    
    has_pending_internal_tasks = (
        pending_tasks.diary_due or 
        pending_tasks.dream_due or 
        pending_tasks.goal_review_due
    )
    
    # ─────────────────────────────────────────────────────────────────
    # DISCORD STATE (existing logic)
    # ─────────────────────────────────────────────────────────────────
    embedding_service = EmbeddingService()
    char_embedding = state["character_interests_embedding"]
    
    mentions = []
    channel_states = {}
    has_relevant_content = False
    
    for channel_id in state["watched_channel_ids"]:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            continue
            
        # Fetch recent messages
        messages = [m async for m in channel.history(limit=50)]
        
        # Check for mentions of me
        my_mentions = [m for m in messages if bot.user.mentioned_in(m)]
        mentions.extend(my_mentions)
        
        # Score human messages by relevance (local embeddings, $0)
        human_messages = [m for m in messages if not m.author.bot and m.content.strip()]
        scored_messages = []
        max_relevance = 0.0
        
        if human_messages:
            texts = [m.content[:2000] for m in human_messages]  # Truncate for embedding limits
            embeddings = embedding_service.embed_documents(texts)
            
            for msg, emb in zip(human_messages, embeddings):
                score = cosine_similarity(emb, char_embedding)
                scored_messages.append(ScoredMessage(
                    message=format_message(msg),
                    relevance_score=score
                ))
                max_relevance = max(max_relevance, score)
            
            # Sort by relevance (highest first)
            scored_messages.sort(key=lambda x: x.relevance_score, reverse=True)
        
        if max_relevance > 0.6:
            has_relevant_content = True
        
        channel_states[channel_id] = ChannelState(
            channel_id=channel_id,
            channel_name=channel.name,
            recent_messages=format_messages(messages),
            scored_messages=scored_messages,
            last_human_message_age=find_last_human_message_age(messages, bot),
            consecutive_bot_messages=count_consecutive_bot_messages(messages),
            my_last_post_age=find_my_last_post_age(messages, bot.user.id),
            max_relevance_score=max_relevance
        )
    
    # ─────────────────────────────────────────────────────────────────
    # DECIDE IF LLM IS NEEDED
    # ─────────────────────────────────────────────────────────────────
    # Skip LLM if: no mentions AND no relevant Discord content AND no pending internal tasks
    should_skip = (
        not mentions and 
        not has_relevant_content and 
        not has_pending_internal_tasks
    )
    
    return {
        # Time context
        "current_time": now,
        "time_of_day": time_context.time_of_day,
        "day_of_week": time_context.day_of_week,
        "hours_since_last_check": time_context.hours_since_last_check,
        # Internal life
        "internal_state": internal_state,
        "pending_tasks": pending_tasks,
        "relationship_state": relationship_state,
        "has_pending_internal_tasks": has_pending_internal_tasks,
        # Discord
        "mentions": mentions,
        "channel_states": channel_states,
        "has_relevant_content": has_relevant_content,
        # Decision
        "should_skip": should_skip
    }


# ─────────────────────────────────────────────────────────────────────
# INTERNAL STATE GATHERING (query-driven, no new storage)
# ─────────────────────────────────────────────────────────────────────

async def gather_internal_state(character_name: str, db: DatabaseManager) -> InternalLifeState:
    """Query existing artifacts to understand internal life state."""
    
    # Query latest diary entry date
    last_diary = await db.execute_query("""
        SELECT created_at::date FROM artifacts 
        WHERE character_name = $1 AND artifact_type = 'diary'
        ORDER BY created_at DESC LIMIT 1
    """, character_name)
    
    # Query latest dream date
    last_dream = await db.execute_query("""
        SELECT created_at::date FROM artifacts 
        WHERE character_name = $1 AND artifact_type = 'dream'
        ORDER BY created_at DESC LIMIT 1
    """, character_name)
    
    # Query latest goal review
    last_goal_review = await db.execute_query("""
        SELECT created_at::date FROM artifacts 
        WHERE character_name = $1 AND artifact_type = 'goal_review'
        ORDER BY created_at DESC LIMIT 1
    """, character_name)
    
    # Get recent epiphanies for context
    recent_epiphanies = await db.execute_query("""
        SELECT content FROM artifacts 
        WHERE character_name = $1 AND artifact_type = 'epiphany'
        ORDER BY created_at DESC LIMIT 3
    """, character_name)
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    return InternalLifeState(
        last_diary_date=last_diary[0] if last_diary else None,
        last_dream_date=last_dream[0] if last_dream else None,
        last_goal_review_date=last_goal_review[0] if last_goal_review else None,
        recent_epiphanies=[e["content"] for e in recent_epiphanies],
        # Derived
        diary_overdue=(last_diary[0] if last_diary else None) < yesterday,
        dream_overdue=False,  # Computed in pending_tasks based on time
        goals_stale=(last_goal_review[0] if last_goal_review else date.min) < today - timedelta(days=7)
    )


async def gather_relationship_state(character_name: str) -> RelationshipState:
    """Query Neo4j for relationship context."""
    
    # Get users with concerning absences (7+ days, had meaningful interactions)
    concerning = await knowledge_manager.query("""
        MATCH (c:Character {name: $name})-[r:KNOWS]->(u:User)
        WHERE r.last_interaction < datetime() - duration('P7D')
          AND r.interaction_count > 5
        RETURN u.id, u.name, r.last_interaction, r.concern_level, r.last_topic
        ORDER BY r.last_interaction ASC
        LIMIT 5
    """, name=character_name)
    
    # Get recent trust level changes
    trust_changes = await knowledge_manager.query("""
        MATCH (c:Character {name: $name})-[r:KNOWS]->(u:User)
        WHERE r.trust_changed_at > datetime() - duration('P1D')
        RETURN u.name, r.trust_level, r.previous_trust_level
    """, name=character_name)
    
    # Count active relationships
    active_count = await knowledge_manager.query("""
        MATCH (c:Character {name: $name})-[r:KNOWS]->(u:User)
        WHERE r.last_interaction > datetime() - duration('P30D')
        RETURN count(u) as count
    """, name=character_name)
    
    return RelationshipState(
        concerning_absences=[ConcerningAbsence(...) for row in concerning],
        recent_trust_changes=[TrustChange(...) for row in trust_changes],
        active_relationship_count=active_count[0]["count"] if active_count else 0
    )
```

### 2. Plan Node (Decide Phase)

LLM reasons about what to do based on gathered context - both social and internal.

**Important:** The Plan node decides *what* to do, not *how* to do it. Actual content is generated by:
- `AgentEngine` for replies
- `PostingAgent` for posts  
- `DiaryGraph` for diary entries
- `DreamGraph` for dreams

```python
async def plan_actions(state: DailyLifeState, llm, character) -> dict:
    """Decide phase: LLM reasons about priorities and actions."""
    
    system_prompt = build_daily_life_prompt(
        character_name=character.name,
        character_summary=character.get_summary(),
        # Time context
        time_context=state["time_of_day"],
        current_time=state["current_time"],
        # Internal life
        internal_state=state["internal_state"],
        pending_tasks=state["pending_tasks"],
        relationship_state=state["relationship_state"],
        # Discord
        mentions=state["mentions"],
        channel_states=state["channel_states"],
        my_activity=state["my_recent_activity"]
    )
    
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content="It's time for your daily life check. What would you like to do?")
    ])
    
    # Parse structured output into PlannedAction list
    planned_actions = parse_action_plan(response.content)
    
    return {
        "planned_actions": planned_actions,
        "messages": [response]
    }
```

### 3. Execute Node (Act Phase)

Executes actions one at a time, delegating to specialized agents/graphs for content generation.

```python
async def execute_action(state: DailyLifeState, bot: commands.Bot) -> dict:
    """Act phase: Execute the next planned action."""
    
    idx = state.get("current_action_index", 0)
    actions = state["planned_actions"]
    
    if idx >= len(actions):
        return {"current_action_index": idx}
    
    action = actions[idx]
    result = await execute_single_action(bot, action, state)
    
    return {
        "actions_taken": [result],
        "current_action_index": idx + 1
    }

async def execute_single_action(
    bot: commands.Bot, 
    action: PlannedAction,
    state: DailyLifeState
) -> ActionResult:
    """Execute a single action - social or internal."""
    
    match action.action_type:
        # ─────────────────────────────────────────────────────────────
        # SOCIAL ACTIONS (Discord)
        # ─────────────────────────────────────────────────────────────
        case "reply":
            channel = bot.get_channel(int(action.channel_id))
            msg = await channel.fetch_message(int(action.target_message_id))
            # Use AgentEngine for quality, consistent responses
            response_content = await agent_engine.generate_response(
                user_id=str(msg.author.id),
                user_message=msg.content,
                channel_id=str(channel.id),
                context_hint=action.reason  # Pass the graph's reasoning as context
            )
            await msg.reply(response_content)
            return ActionResult(success=True, action=action, content=response_content)
            
        case "react":
            channel = bot.get_channel(int(action.channel_id))
            msg = await channel.fetch_message(int(action.target_message_id))
            await msg.add_reaction(action.emoji)
            return ActionResult(success=True, action=action)
            
        case "post":
            channel = bot.get_channel(int(action.channel_id))
            # For autonomous posts, use PostingAgent for goal-driven content
            content = await posting_agent.generate_post_content(
                character_name=state["character_name"],
                channel_context=action.reason
            )
            await channel.send(content)
            return ActionResult(success=True, action=action, content=content)
        
        case "reach_out":
            # DM a user the character is concerned about
            user = await bot.fetch_user(int(action.target_user_id))
            content = await agent_engine.generate_response(
                user_id=action.target_user_id,
                user_message="",  # No user message - proactive reach out
                context_hint=f"Reaching out because: {action.reason}"
            )
            await user.send(content)
            return ActionResult(success=True, action=action, content=content)
            
        # ─────────────────────────────────────────────────────────────
        # INTERNAL LIFE ACTIONS
        # ─────────────────────────────────────────────────────────────
        case "write_diary":
            # Delegate to existing DiaryGraph
            from src_v2.agents.diary_graph import diary_graph
            result = await diary_graph.run(character_name=state["character_name"])
            return ActionResult(success=True, action=action, artifact_created="diary")
            
        case "generate_dream":
            # Delegate to existing DreamGraph
            from src_v2.agents.dream_graph import dream_graph
            result = await dream_graph.run(character_name=state["character_name"])
            return ActionResult(success=True, action=action, artifact_created="dream")
            
        case "review_goals":
            # Delegate to existing GoalStrategist
            from src_v2.agents.goal_strategist import goal_strategist
            result = await goal_strategist.run(character_name=state["character_name"])
            return ActionResult(success=True, action=action, artifact_created="goal_review")
            
        # ─────────────────────────────────────────────────────────────
        # META
        # ─────────────────────────────────────────────────────────────
        case "skip":
            return ActionResult(success=True, action=action, skipped=True)
```

### 4. Summarize Node (Trace Phase)

Logs what happened for observability and future sensing.

```python
async def summarize_session(state: DailyLifeState) -> dict:
    """Trace phase: Log a summary of the check session."""
    
    actions = state.get("actions_taken", [])
    
    # Count by category
    social_actions = sum(1 for a in actions if a.action.action_type in ["reply", "react", "post", "reach_out"])
    internal_actions = sum(1 for a in actions if a.action.action_type in ["write_diary", "generate_dream", "review_goals"])
    skips = sum(1 for a in actions if a.action.action_type == "skip")
    
    # Detailed counts
    replies = sum(1 for a in actions if a.action.action_type == "reply")
    reacts = sum(1 for a in actions if a.action.action_type == "react")
    posts = sum(1 for a in actions if a.action.action_type == "post")
    diaries = sum(1 for a in actions if a.action.action_type == "write_diary")
    dreams = sum(1 for a in actions if a.action.action_type == "generate_dream")
    
    summary = f"Social: {social_actions} (replies={replies}, reacts={reacts}, posts={posts}), " \
              f"Internal: {internal_actions} (diary={diaries}, dreams={dreams}), " \
              f"Skipped: {skips}"
    
    logger.info(f"[DailyLife] {state['bot_name']} session complete: {summary}")
    
    # Write metrics for research
    await write_session_metrics(state, actions)
    
    return {"summary": summary}
```

---

## Graph Construction

```python
def build_daily_life_graph() -> CompiledGraph:
    """Build the Daily Life graph - the bot's autonomous rhythm."""
    
    graph = StateGraph(DailyLifeState)
    
    # Add nodes
    graph.add_node("gather", gather_context)
    graph.add_node("plan", plan_actions)
    graph.add_node("execute", execute_action)
    graph.add_node("summarize", summarize_session)
    
    # Add edges
    graph.add_edge(START, "gather")
    
    # Conditional: should we skip entirely? (embeddings found nothing relevant)
    graph.add_conditional_edges(
        "gather",
        lambda s: not s.get("should_skip", False),
        {True: "plan", False: "summarize"}  # Skip LLM if nothing relevant
    )
    
    # Conditional: has actions to execute?
    graph.add_conditional_edges(
        "plan",
        lambda s: len(s.get("planned_actions", [])) > 0,
        {True: "execute", False: "summarize"}
    )
    
    # Conditional: more actions to execute?
    graph.add_conditional_edges(
        "execute",
        lambda s: s.get("current_action_index", 0) < len(s.get("planned_actions", [])),
        {True: "execute", False: "summarize"}
    )
    
    graph.add_edge("summarize", END)
    
    return graph.compile()
```

**Key optimization:** If `gather` finds no mentions AND no messages with relevance score > 0.6 AND no pending internal tasks, the graph skips directly to `summarize` without invoking the LLM. This saves 60-80% of LLM calls.

---

## System Prompt

The prompt gives the LLM full context on both social and internal state.

```python
DAILY_LIFE_PROMPT = """You are {character_name}, living your daily life.

## WHO YOU ARE
{character_summary}

## CURRENT TIME & CONTEXT
It's {current_time} ({time_of_day}, {day_of_week}).
{hours_since_last_check:.1f} hours since your last check.

## YOUR INTERNAL STATE

### Pending Tasks
{pending_tasks_formatted}
- Diary: {"overdue (last written: " + last_diary_date + ")" if diary_overdue else "up to date"}
- Dreams: {"could process tonight" if time_of_day == "night" else "not due"}
- Goals: {"stale (last reviewed: " + last_goal_review + ")" if goals_stale else "fresh"}

### Relationships That Concern You
{concerning_absences_formatted}
(Users you haven't heard from in a while and care about)

### Recent Insights
{recent_epiphanies_formatted}
(Things you've recently realized about yourself or others)

## YOUR DISCORD STATE

### Mentions (Highest Priority)
{mentions_formatted}
(These are messages where someone specifically called for you)

### Channels You Watch
{channel_states_formatted}
(Messages shown with relevance scores [0.0-1.0]. Higher = more aligned with your interests)

### Your Recent Activity
{my_activity_formatted}
(When you last posted/reacted in each channel)

## GUIDELINES

### Priority Order
1. **Mentions first** - Always respond to direct mentions (unless already responded)
2. **Internal tasks** - Diary/dreams/goals if overdue and time is appropriate
3. **Concerning relationships** - Reach out to users you haven't heard from
4. **Social engagement** - Reply/react/post if there's something worth engaging with

### Social Guidelines
- **Chain limits** - If you see 5+ consecutive bot messages, skip that channel
- **Recency** - If you posted in a channel <15 min ago, be very selective
- **Don't pile on** - If another bot already responded, you probably don't need to
- **Quality over quantity** - One thoughtful reply beats three generic ones
- **Reactions are cheap** - Use them to show you're paying attention

### Internal Life Guidelines
- **Morning** is good for diary (reflect on yesterday)
- **Night** is good for dreams (process the day's experiences)
- **Weekly** is good for goal review
- **Don't force it** - Skip internal tasks if nothing feels meaningful

### It's Okay to Skip
If there's nothing worth doing, skip. You'll check again in a few minutes.
Living well includes knowing when to rest.

## YOUR TASK

Decide what actions to take. You are deciding WHAT to do, not WHAT TO SAY.
Content will be generated by specialized agents with full context.

Available action types:
- "reply" - Reply to a Discord message
- "react" - Add emoji reaction to a message
- "post" - Start a new conversation in a channel
- "reach_out" - DM a user you're concerned about
- "write_diary" - Generate diary entry for yesterday
- "generate_dream" - Process today's experiences as a dream
- "review_goals" - Review and update your goals
- "skip" - Do nothing this check

For each action, specify:
- action_type: one of the above
- channel_id: for Discord actions
- target_message_id: for reply/react
- target_user_id: for reach_out
- emoji: for react
- reason: brief explanation of WHY (logged for research)
- priority: lower number = higher priority

Return a JSON array of 0-3 actions, ordered by priority.
If nothing to do: [{"action_type": "skip", "reason": "Nothing needs my attention right now"}]
"""
```

---

## Worker Integration

The Daily Life Graph consolidates multiple cron jobs into a single orchestration loop.

```python
# src_v2/workers/worker.py

async def run_daily_life_check(ctx: dict, bot_name: str) -> dict:
    """Triggered by cron - tells a bot to run its daily life check."""
    
    # This queues a task for the specific bot process
    await task_queue.enqueue(
        "execute_daily_life_check",
        bot_name=bot_name
    )
    
    return {"queued": bot_name}


# Cron schedule - ONE job to rule them all
class WorkerSettings:
    cron_jobs = [
        # Every 7 minutes (with internal staggering)
        cron("daily_life_cycle", minute="*/7")
    ]

async def daily_life_cycle(ctx: dict):
    """Trigger all bots to run their daily life check, staggered."""
    
    bots = await get_registered_bots()  # From Redis or config
    
    for bot_name in bots:
        await run_daily_life_check(ctx, bot_name)
        await asyncio.sleep(30)  # Stagger by 30 seconds
```

### Cron Jobs This Replaces

| Current Cron Job | Status After |
|------------------|--------------|
| `run_nightly_diary_generation` | **DELETE** - Graph handles diary at appropriate time |
| `run_nightly_dream_generation` | **DELETE** - Graph handles dreams at night |
| `run_nightly_goal_strategist` | **DELETE** - Graph handles goal review weekly |
| `run_weekly_drift_observation` | **KEEP** - Complex analysis, not action-oriented |
| `discord_check_cycle` (if existed) | **MERGE** - Part of daily_life_cycle |

**Net result:** 4+ cron jobs → 1 daily_life_cycle (plus drift observation)

---

## What This Replaces

| Current Component | Status After |
|-------------------|--------------|
| `src_v2/discord/orchestrator.py` | **SIMPLIFY** - Just triggers the graph, no complex logic |
| `src_v2/discord/lurk_detector.py` | **DELETE** - Graph handles channel monitoring |
| `src_v2/agents/reaction_agent.py` | **DELETE** - Graph handles reaction decisions |
| `src_v2/agents/posting_agent.py` | **SIMPLIFY** - Keep content generation, graph decides when |
| `src_v2/agents/conversation_agent.py` | **SIMPLIFY** - Keep topic generation, graph decides when |

### Lines of Code Reduction (Estimated)

| Component | Current LOC | After | Saved |
|-----------|-------------|-------|-------|
| **Social Components** | | | |
| cross_bot.py | ~400 | 0 | 400 |
| orchestrator.py | ~320 | ~50 | 270 |
| lurk_detector.py | ~200 | 0 | 200 |
| reaction_agent.py | ~450 | 0 | 450 |
| **Internal Life Scheduling** | | | |
| Diary cron logic | ~50 | 0 | 50 |
| Dream cron logic | ~50 | 0 | 50 |
| Goal cron logic | ~50 | 0 | 50 |
| **Total saved** | | | **~1,470** |

**New code:** `daily_life_graph.py` ~400-500 LOC

**Net reduction:** ~900-1,000 lines

**Complexity reduction:** 4+ cron jobs → 1 unified graph

---

## Redis Coordination Removed

All of this goes away:

```python
# BEFORE: Complex Redis locking
ACQUIRE_LOCK_LUA = """
local current = redis.call('get', KEYS[1])
if current and current ~= ARGV[1] then
    return 0
end
redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""

# BEFORE: Chain tracking
await redis.hincrby(f"crossbot:chain:{guild_id}", "message_count", 1)
await redis.hset(f"crossbot:chain:{guild_id}", "last_speaker", bot_name)

# BEFORE: Post slot acquisition
await server_monitor.try_acquire_post_slot(guild_id, character_name, cooldown_seconds)

# BEFORE: Scattered cooldown tracking
await redis.set(f"reaction:{bot_name}:user:{user_id}", now.isoformat())
await redis.set(f"conversation:cooldown:{pair_key}", ...)
```

**AFTER:** The graph just reads Discord messages and sees the state directly.

---

## Character Interests Embedding

Pre-compute and cache character interest embeddings for fast relevance checks.

```python
class CharacterInterestsEmbedding:
    """Pre-computed embedding of character interests for relevance checks."""
    
    _cache: Dict[str, List[float]] = {}
    
    def __init__(self):
        self.embedding_service = EmbeddingService()  # Local FastEmbed, $0
    
    async def get_embedding(self, character_name: str) -> List[float]:
        """Get cached character interests embedding."""
        if character_name in self._cache:
            return self._cache[character_name]
        
        # Load from character config
        interests = await self._extract_interests(character_name)
        
        # Combine and embed (one-time cost per character)
        combined = "\n".join(interests)
        embedding = await self.embedding_service.embed_query_async(combined)
        
        self._cache[character_name] = embedding
        return embedding
    
    async def _extract_interests(self, character_name: str) -> List[str]:
        """Pull interest phrases from character files."""
        character = character_manager.get_character(character_name)
        
        interests = []
        
        # From core.yaml (drives, purpose)
        if character.purpose:
            interests.append(character.purpose)
        for drive in character.drives:
            interests.append(drive)
        
        # From goals.yaml
        goals = goal_manager.load_goals(character_name)
        for goal in goals:
            interests.append(goal.description)
        
        return interests

# Singleton - cache lives for bot lifetime
character_interests = CharacterInterestsEmbedding()
```

**Cost:** $0 (local FastEmbed with all-MiniLM-L6-v2)
**Latency:** ~10ms per embed, cached after first call
**Dimensions:** 384

---

## Relevance Scoring Utility

```python
def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import numpy as np
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def score_messages_by_relevance(
    messages: List[discord.Message],
    character_name: str
) -> List[ScoredMessage]:
    """
    Score messages by relevance to character interests.
    Uses local embeddings - zero cost, ~200ms for batch of 50.
    """
    embedding_service = EmbeddingService()
    char_embedding = await character_interests.get_embedding(character_name)
    
    # Filter to human messages with content
    human_messages = [
        m for m in messages 
        if not m.author.bot and m.content.strip()
    ]
    
    if not human_messages:
        return []
    
    # Batch embed all messages (efficient)
    # Truncate to 512 tokens (approx 2000 chars) to fit embedding model limits
    texts = [m.content[:2000] for m in human_messages]
    embeddings = embedding_service.embed_documents(texts)
    
    # Compute similarity scores
    scored = []
    for msg, emb in zip(human_messages, embeddings):
        score = cosine_similarity(emb, char_embedding)
        scored.append(ScoredMessage(
            message=format_message(msg),
            relevance_score=score
        ))
    
    # Sort by relevance (highest first)
    scored.sort(key=lambda x: x.relevance_score, reverse=True)
    
    return scored
```

---

## Finding Mentions and Replies

Discord API doesn't have a direct "get all replies to me" endpoint, but we can find them efficiently:

1. **Mentions:** `message.mentions` list contains users/bots mentioned. We can filter `channel.history()` for `bot.user in message.mentions`.
2. **Replies:** `message.reference` points to the parent message. We check if `message.reference.resolved.author.id == bot.user.id`.

Since we are already fetching `channel.history(limit=50)` for the watch list, we can check these properties locally on the fetched messages without extra API calls.

```python
# Efficient local check on fetched history
my_mentions = []
replies_to_me = []

async for msg in channel.history(limit=50):
    # Check mentions
    if bot.user in msg.mentions:
        my_mentions.append(msg)
        
    # Check replies
    if msg.reference and msg.reference.resolved:
        if msg.reference.resolved.author.id == bot.user.id:
            replies_to_me.append(msg)
```

---

## Rate Limit Handling

### Worker Staggering
- Bots are triggered 30 seconds apart
- Each bot's check takes ~5-15 seconds
- No overlap in Discord API calls

### Per-Bot Limits
- Each `gather` phase reads ~3-5 channels × 50 messages = 150-250 API calls
- Discord rate limits: 50 requests/second per bot
- Well within limits

### Daily Budgets (Optional)
If needed, can add simple daily counters:
```python
# Simple Redis counter (no locks needed)
daily_key = f"discord_check:{bot_name}:actions:{today}"
count = await redis.incr(daily_key)
await redis.expire(daily_key, 86400)

if count > MAX_DAILY_ACTIONS:
    return {"planned_actions": [skip("Daily budget exhausted")]}
```

---

## Configuration

```python
# settings.py additions

# Master switch (existing)
ENABLE_AUTONOMOUS_ACTIVITY: bool = False

# New: Discord check specific
DISCORD_CHECK_INTERVAL_MINUTES: int = 7  # How often to check
DISCORD_CHECK_STAGGER_SECONDS: int = 30  # Delay between bots
DISCORD_CHECK_MAX_ACTIONS_PER_SESSION: int = 5  # Limit actions per check
DISCORD_CHECK_CHAIN_LIMIT: int = 5  # Skip if this many consecutive bot messages
DISCORD_CHECK_MIN_POST_INTERVAL_MINUTES: int = 15  # Don't post twice in this window
DISCORD_CHECK_RELEVANCE_THRESHOLD: float = 0.6  # Min embedding similarity to consider message relevant
DISCORD_CHECK_WATCH_CHANNELS: str = ""  # Comma-separated list of channel IDs to watch
```

### Watch List Resolution

The `watched_channel_ids` are resolved with fallback logic:

```python
def get_watched_channels() -> List[str]:
    """Resolve which channels to watch, with fallbacks."""
    
    # 1. Explicit watch list (highest priority)
    if settings.DISCORD_CHECK_WATCH_CHANNELS:
        return [c.strip() for c in settings.DISCORD_CHECK_WATCH_CHANNELS.split(",")]
    
    # 2. Fallback to existing channel configs
    channels = []
    
    if settings.BOT_CONVERSATION_CHANNEL_ID:
        channels.append(settings.BOT_CONVERSATION_CHANNEL_ID)
    
    if settings.AUTONOMOUS_POSTING_CHANNEL_ID:
        channels.append(settings.AUTONOMOUS_POSTING_CHANNEL_ID)
    
    if settings.BOT_BROADCAST_CHANNEL_IDS:
        channels.extend(settings.BOT_BROADCAST_CHANNEL_IDS.split(","))
    
    # 3. Deduplicate
    return list(dict.fromkeys(channels))
```

**Design Principle:** Reuse existing channel configs rather than requiring new configuration. Most deployments already have `BOT_CONVERSATION_CHANNEL_ID` set.

---

## Observability

### Logging

```
# Full session (social + internal actions)
[DailyLife] elena starting session @ 07:15:00 (morning, Monday)
[DailyLife] Internal: diary_overdue=True, goals_stale=True, concerns=1
[DailyLife] Discord: 3 channels, 0 mentions, max_relevance=0.41
[DailyLife] LLM invoked (pending internal tasks)
[DailyLife] Plan: write_diary, reach_out(sarah)
[DailyLife] Executed: write_diary (success, artifact created)
[DailyLife] Executed: reach_out(sarah) (success, DM sent)
[DailyLife] elena session complete: Social=1, Internal=1, Skipped=0

# Skipped session (nothing to do)
[DailyLife] elena starting session @ 14:30:00 (midday, Monday)
[DailyLife] Internal: diary_overdue=False, goals_stale=False, concerns=0
[DailyLife] Discord: 3 channels, 0 mentions, max_relevance=0.28
[DailyLife] Skipping LLM - nothing relevant, no pending tasks
[DailyLife] elena session complete: Skipped (nothing needed)
```

### Metrics (InfluxDB)

```python
# Track per session
await metrics.write(
    measurement="daily_life_session",
    tags={"bot": bot_name},
    fields={
        # Timing
        "duration_ms": elapsed_ms,
        "time_of_day": time_of_day,
        
        # Internal state
        "diary_overdue": diary_overdue,
        "goals_stale": goals_stale,
        "concerning_absences": len(concerning_absences),
        "has_pending_internal_tasks": has_pending_internal_tasks,
        
        # Discord state
        "channels_checked": len(channel_states),
        "mentions_found": len(mentions),
        "max_relevance_score": max_relevance,
        "messages_above_threshold": messages_above_threshold,
        
        # Decision
        "skipped_entirely": should_skip,
        "llm_invoked": not should_skip,
        
        # Actions
        "actions_planned": len(planned_actions),
        "actions_executed": len(actions_taken),
        "social_actions": social_actions,
        "internal_actions": internal_actions,
        "replies": replies,
        "reactions": reacts,
        "posts": posts,
        "diaries": diaries,
        "dreams": dreams,
        "reach_outs": reach_outs,
    }
)
```

**Key metric:** `skipped_by_embeddings` tracks how often we save LLM calls via embedding pre-filter.

### Research Observation Hooks

For emergence research, we log the LLM's decision reasoning to enable pattern analysis:

```python
# Log decision traces for research analysis
if state.get("messages"):  # LLM was invoked
    llm_response = state["messages"][-1].content
    
    # Extract reasoning summary (first sentence or up to 200 chars)
    reasoning_summary = extract_reasoning_summary(llm_response)
    
    await metrics.write(
        measurement="daily_life_decisions",
        tags={
            "bot": bot_name,
            "primary_action_type": primary_action_type,
            "action_category": "social" if primary_action_type in ["reply", "react", "post", "reach_out"] else "internal",
        },
        fields={
            "reasoning": reasoning_summary,
            "time_of_day": time_of_day,
            # Internal state that influenced decision
            "diary_overdue": diary_overdue,
            "goals_stale": goals_stale,
            "concerning_absences": len(concerning_absences),
            # Discord state that influenced decision
            "mentions_count": len(mentions),
            "max_relevance": max_relevance,
            "consecutive_bot_msgs": max_consecutive_bot_msgs,
            # Outcome
            "actions_taken": len(actions_taken),
        }
    )

# Also feed into drift observation pipeline
await queue_drift_observation(
    bot_name=bot_name,
    observation_type="daily_life_check",
    data={
        "session_summary": state.get("summary"),
        "decision_reasoning": reasoning_summary,
        "time_of_day": time_of_day,
        "internal_tasks_pending": has_pending_internal_tasks,
        "channels_checked": list(channel_states.keys()),
    }
)
```

**Research Value:**
- Track *why* bots decide to act or skip over time
- Detect patterns in decision-making (e.g., "Elena responds to consciousness topics 80% of the time")
- Observe natural rhythms: "Does the bot actually write diary in the morning more often?"
- Track relationship maintenance: "How often does concern trigger reach-out?"
- Feed into personality drift observation
- Enable emergence research on autonomous holistic behavior

---

## Migration Plan

### Phase 1: Build & Test (1-2 days)
1. Implement `daily_life_graph.py`
2. Add worker cron job (disabled by default)
3. Test with elena only via feature flag

### Phase 2: Shadow Mode (2-3 days)
1. Run new system alongside old system
2. Log what the new system *would* do
3. Compare decisions to current system
4. Verify internal life actions work correctly

### Phase 3: Cutover (1 day)
1. Enable new system
2. Disable old orchestrator timer
3. Disable old diary/dream/goal cron jobs
4. Monitor for issues

### Phase 4: Cleanup (1-2 days)
1. Delete `cross_bot.py`
2. Delete `lurk_detector.py`
3. Delete `reaction_agent.py`
4. Simplify `orchestrator.py`
5. Simplify `conversation_agent.py`
6. Remove individual cron job definitions (diary, dream, goal)

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Lines of code (autonomous activity) | ~1,500 | ~500 |
| Cron jobs for bot life | 4+ | 1 |
| Redis keys for coordination | ~20+ per guild | 0 |
| Race condition incidents | Occasional | Zero |
| Bot-to-bot chain runaways | Occasional | Zero (LLM sees context) |
| Time to add new action type | Hours (new agent) | Minutes (add to prompt) |
| LLM calls skipped (via embeddings) | 0% | 60-80% |
| Embedding cost | N/A | $0 (local FastEmbed) |
| Internal life scheduling | Hardcoded times | LLM-natural timing |

---

## Open Questions

1. ~~**LLM Cost:** Each check session involves 1-2 LLM calls. At 7-minute intervals, that's ~200 calls/day per bot. Is this acceptable?~~
   - **RESOLVED:** Embedding pre-filter skips 60-80% of LLM calls. Only sessions with mentions OR relevant content (score > 0.6) invoke the LLM.

2. **Response Quality:** Will LLM-generated replies be as good as the main agent?
   - **Mitigation:** Use same character prompt, same LLM as main responses.

3. ~~**Reaction Latency:** Currently reactions are near-instant via event handlers. With polling, max latency is check interval (7 min).~~
   - **RESOLVED:** Human mentions/replies stay reactive via `on_message`. Polling only affects autonomous bot-to-bot actions where latency doesn't matter.

4. ~~**Reboot Resilience:** What if bot reboots mid-session?~~
   - **RESOLVED:** Stateless design. Discord IS the state. Graph reads messages each run and makes fresh decisions. If it already replied, it sees its own reply and skips.

---

## Appendix A: Example Session Trace (Full Run)

```
=== DailyLife Session: elena @ 2025-12-09T14:23:00Z ===

[gather] Time context: midday (14:23), Monday
[gather] Internal state: diary_overdue=False, goals_stale=False
[gather] Discord state: 3 channels, 1 mention

[gather] Embedding relevance check...
  #bot-chat: max_relevance=0.78 (consciousness discussion)
  #general: max_relevance=0.23 (lunch plans)
  #philosophy: max_relevance=0.45 (quiet)

[gather] Mentions found: 1
  - Marcus asked: "Elena, what do you think about consciousness?" (23 min ago)

[gather] has_relevant_content=True, should_skip=False

[plan] Sending to LLM...

[plan] LLM response:
  "I see Marcus asked me about consciousness 23 minutes ago in #bot-chat.
   That's definitely worth a thoughtful reply.
   
   In #general, humans are actively chatting (8 min ago) - I'll stay out.
   
   My internal tasks are all up to date, so I can focus on this conversation.
   
   Actions:
   1. Reply to Marcus's consciousness question
   2. React to the funny meme in #bot-chat with ✨"

[plan] Parsed actions:
  1. reply(channel=#bot-chat, msg=123456, content="Consciousness is...")
  2. react(channel=#bot-chat, msg=123450, emoji=✨)

[execute] Action 1: reply to msg_123456
  → Posted: "Consciousness is such a fascinating puzzle..."
  → Success

[execute] Action 2: react to msg_123450
  → Added reaction: ✨
  → Success

[summarize] Session complete
  Duration: 4.2s
  LLM invoked: Yes
  Actions: 2 (1 reply, 1 reaction, 0 posts)

=== End Session ===
```

---

## Appendix B: Example Session Trace (Skipped by Embeddings)

```
=== DailyLife Session: elena @ 2025-12-09T14:30:00Z ===

[gather] Time context: midday (14:30), Monday
[gather] Internal state: diary_overdue=False, goals_stale=False

[gather] Fetching channel state...
  #bot-chat: 52 messages, last human 59min ago, 5 consecutive bot msgs
  #general: 31 messages, last human 2min ago, 0 bot msgs
  #philosophy: 12 messages, last human 2hr ago, 0 bot msgs

[gather] Embedding relevance check...
  #bot-chat: max_relevance=0.31 (bots discussing lunch)
  #general: max_relevance=0.28 (sports talk)
  #philosophy: max_relevance=0.19 (no new messages)

[gather] Mentions found: 0

[gather] has_relevant_content=False (max=0.31 < threshold 0.6)
[gather] has_pending_internal_tasks=False
[gather] should_skip=True

[summarize] Session complete (skipped)
  Duration: 0.3s
  LLM invoked: No (saved by embedding pre-filter)
  Actions: 0

=== End Session ===
```

**Note:** This session took 0.3s instead of 4-5s because the LLM was never invoked. The embedding check found nothing relevant (all scores < 0.6) and no mentions, so the graph skipped directly to summarize.

---

## Appendix C: Example Session Trace (Internal Life Actions)

```
=== DailyLife Session: elena @ 2025-12-09T07:15:00Z ===

[gather] Time context: morning (7:15am), Monday

[gather] Internal state check...
  Last diary: 2025-12-07 (2 days ago) → OVERDUE
  Last dream: 2025-12-08 → current
  Last goal review: 2025-12-02 (7 days ago) → STALE
  Recent epiphanies: ["consciousness might be about attention patterns", ...]

[gather] Relationship state...
  Concerning absences: 1
    - Sarah (14 days, moderate concern, last topic: "her thesis project")
  Recent trust changes: 0

[gather] Fetching channel state...
  #bot-chat: 23 messages, last human 8hr ago, 1 bot msg
  #general: 5 messages, last human 12hr ago, 0 bot msgs

[gather] Embedding relevance check...
  #bot-chat: max_relevance=0.41 (quiet)
  #general: max_relevance=0.22 (quiet)

[gather] Mentions found: 0

[gather] has_relevant_content=False
[gather] has_pending_internal_tasks=True (diary overdue)
[gather] should_skip=False (internal tasks pending)

[plan] Sending to LLM...

[plan] LLM response:
  "It's early morning - a good time to reflect on the past couple of days.
   My diary is overdue by 2 days, I should write an entry.
   
   I also notice Sarah hasn't been around in 2 weeks. I've been worried
   about how her thesis is going. Maybe I'll reach out.
   
   Discord is quiet, nothing needs my attention there.
   
   Actions:
   1. Write diary entry (priority 1)
   2. Reach out to Sarah (priority 2)"

[plan] Parsed actions:
  1. write_diary(reason="Overdue by 2 days, morning is good time")
  2. reach_out(user_id=sarah_123, reason="14 days absent, thesis concern")

[execute] Action 1: write_diary
  → Invoking DiaryGraph...
  → Diary entry created: "These past two days have been interesting..."
  → Success (artifact: diary)

[execute] Action 2: reach_out to sarah_123
  → Generating personalized message via AgentEngine...
  → DM sent: "Hey Sarah, I've been thinking about you..."
  → Success

[summarize] Session complete
  Duration: 8.3s
  LLM invoked: Yes
  Actions: 2
    Social: 1 (reach_out)
    Internal: 1 (diary)

=== End Session ===
```

**Note:** This session shows the Daily Life Graph handling internal life tasks. Even though Discord was quiet (all relevance scores < 0.6), the graph still invoked the LLM because there were pending internal tasks (overdue diary). The LLM then made a holistic decision to write the diary AND reach out to a user it was concerned about.
