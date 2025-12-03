# Autonomous Server Activity System

**Document Version:** 1.3  
**Created:** November 30, 2025  
**Updated:** December 2, 2025  
**Status:** ✅ Complete (Phases 1-4)  
**Type:** Epic / Feature Roadmap  
**Priority:** 🟢 High (Server Engagement)

---

## Executive Summary

Transform passive bots into active server participants that create organic engagement during quiet periods. Rather than waiting for users to initiate, bots will autonomously:

1. **React to messages** with contextually appropriate emojis
2. **Post original content** (thoughts, observations, questions) driven by character goals
3. **Comment on current events** using web search for stocks, news, trending topics
4. **Engage in bot-to-bot conversations** in public channels
5. **Scale activity inversely to human activity** (quiet = posts, active = reactions)

**Goal:** Make an empty Discord server feel alive and welcoming when real users arrive.

---

## Problem Statement

Current State:
- ✅ Bots respond when mentioned or DMed
- ✅ Lurk detector can respond to relevant topics (ENABLE_CHANNEL_LURKING)
- ✅ Proactive scheduler messages individual users (ENABLE_PROACTIVE_MESSAGING)
- ✅ Cross-bot chat exists for multi-bot conversations (ENABLE_CROSS_BOT_CHAT)
- ✅ Goals system exists in `goals.yaml` for each character
- ✅ Character drives defined in `core.yaml`
- ✅ Web search tool implemented (WEB_SEARCH_TOOL.md)
- ✅ Autonomous posting to public channels (Phase 2)
- ✅ Emoji reactions to other users' messages (Phase 1)
- ❌ No bot-initiated conversations visible to newcomers (Phase 3)
- ❌ Server feels dead when no humans are active

**Result:** New users join, see no activity, and leave.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ActivityOrchestrator                          │
│  (Central coordinator - scales activity to server quietness)     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ ReactionAgent│  │ PostingAgent │  │ConversationAgent│        │
│  │              │  │              │  │  (Bot-to-Bot) │          │
│  │ - Emoji pick │  │ - Goals-driven│  │ - Turn taking │          │
│  │ - Timing     │  │ - Web search │  │ - Topic flow  │          │
│  │ - Rate limit │  │ - Current events│ │ - Natural end │          │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│         │                 │                 │                     │
│         ▼                 ▼                 ▼                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              GoalDrivenTopicSelector                        │ │
│  │  - Reads core.yaml drives + goals.yaml                      │ │
│  │  - Web search for current events (stocks, news, trends)     │ │
│  │  - Matches topics to character expertise                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     ActionQueue (Redis)                      │ │
│  │  - Pending reactions, posts, conversations                  │ │
│  │  - Deduplication, rate limiting, scheduling                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              ActivityExecutor (per-bot process)              │ │
│  │  - Executes queued actions via Discord API                  │ │
│  │  - Respects permissions and rate limits                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Activity Scaling: The Core Principle

**Key Insight:** Bot behavior should inversely correlate with human activity.

| Server State | Human Activity | Bot Behavior |
|--------------|----------------|--------------|
| **Dead Quiet** | 0 messages/30min | Posts, conversations, reactions |
| **Quiet** | 1-3 messages/30min | Occasional posts, reactions |
| **Moderate** | 4-10 messages/30min | Mostly reactions, rare replies |
| **Active** | 10+ messages/30min | Reactions only, let humans lead |
| **Very Active** | 20+ messages/30min | Minimal presence, observe |

```
// Pseudocode: Activity scaling
function calculate_action_budget(human_messages_30min):
  if human_messages_30min == 0:
    return {
      reactions_per_hour: 10,
      posts_probability: 0.4,
      conversation_probability: 0.3,
      reply_probability: 0.1
    }
  elif human_messages_30min <= 3:
    return {
      reactions_per_hour: 5,
      posts_probability: 0.2,
      conversation_probability: 0.1,
      reply_probability: 0.05
    }
  elif human_messages_30min <= 10:
    return {
      reactions_per_hour: 3,
      posts_probability: 0.05,
      conversation_probability: 0.0,
      reply_probability: 0.02
    }
  else:
    return {
      reactions_per_hour: 1,
      posts_probability: 0.0,
      conversation_probability: 0.0,
      reply_probability: 0.01
    }
```

---

## Phase 1: Autonomous Reactions (✅ IMPLEMENTED)

**Status:** Core implementation complete, ready for testing.

**Goal:** Bots react to messages with appropriate emojis without being asked.

### 1.1 ReactionAgent

See `src_v2/agents/reaction_agent.py` - already implemented with:
- Character-specific emoji preferences from `ux.yaml`
- Rate limiting (channel hourly, user cooldown, daily global)
- Sentiment analysis for emoji selection
- Configurable delay for natural feel

### 1.2 Configuration

```yaml
# characters/{name}/ux.yaml
reactions:
  enabled: true
  base_rate: 0.25  # 25% base chance
  topic_boost: 0.4  # +40% for relevant topics
  positive_emojis: ["❤️", "✨", "🔥", "💯"]
  signature_emojis: ["🌊"]  # Character-specific
  reaction_delay_seconds: [3, 12]
```

### 1.3 Enable

```bash
ENABLE_AUTONOMOUS_ACTIVITY=true
ENABLE_AUTONOMOUS_REACTIONS=true
```

---

## Phase 2: Goals-Driven Posting (✅ IMPLEMENTED)

**Status:** Core implementation complete. ActivityOrchestrator + ServerActivityMonitor + PostingAgent implemented Dec 1, 2025.

**Goal:** Bots post content driven by their `goals.yaml` and `core.yaml`, enhanced with current events from web search.

### 2.1 Implementation Summary

**Files Created/Modified:**
- `src_v2/discord/orchestrator.py` - ActivityOrchestrator (background loop, activity scaling)
- `src_v2/intelligence/activity.py` - ServerActivityMonitor (Redis-backed message velocity)
- `src_v2/agents/posting_agent.py` - PostingAgent + GoalDrivenTopicSelector
- `src_v2/broadcast/manager.py` - Added `target_channel_id` for guild-specific posting
- `src_v2/config/settings.py` - Added `ENABLE_AUTONOMOUS_POSTING` flag

**How It Works:**
1. `ServerActivityMonitor` tracks messages per minute per guild using Redis sorted sets
2. `ActivityOrchestrator` checks every 15 minutes (+jitter) for quiet guilds
3. If guild is "dead quiet" (<0.1 msg/min): 70% chance to trigger post
4. If guild is "quiet" (<0.5 msg/min): 30% chance to trigger post
5. `PostingAgent` selects topic from character's `goals.yaml` (weighted by priority)
6. Optional web search for "expertise" or "current_events" categories
7. LLM generates casual 1-3 sentence post in character voice
8. Post is queued via `BroadcastManager` and delivered to the guild's best channel

### 2.2 Enable

```bash
ENABLE_AUTONOMOUS_POSTING=true
```

### 2.3 GoalDrivenTopicSelector

Leverages existing character configuration to select what to post about:

```
class GoalDrivenTopicSelector:
    // Selects topics for autonomous posts based on character identity
    
    function select_topic(character) -> Topic:
        // 1. Load character's goals and drives
        goals = load_goals(character.name)  // from goals.yaml
        drives = load_drives(character.name)  // from core.yaml
        
        // 2. Weight by drive intensity
        weighted_categories = {}
        for goal in goals:
            category = goal.category  // "expertise", "philosophy", "relationship"
            drive_weight = get_drive_weight(drives, category)
            weighted_categories[category] += goal.priority * drive_weight
        
        // 3. Select category probabilistically
        category = weighted_random(weighted_categories)
        
        // 4. Pick specific topic from category
        if category == "expertise":
            return select_expertise_topic(character, goals)
        elif category == "current_events":
            return await fetch_current_event_topic(character)
        else:
            return select_musing_topic(character, category)
```

### 2.2 Character Goal → Post Topic Mapping

| Character | Goals (from goals.yaml) | Post Topics |
|-----------|-------------------------|-------------|
| **Elena** | share_expertise, discuss_ocean, inspire_conservation | Marine biology facts, ocean news, conservation updates |
| **Aetheris** | explore_consciousness_nature, invite_philosophical_exploration | AI news, philosophy musings, consciousness questions |
| **Dotty** | (varies) | Tech news, coding tips, developer humor |
| **Gabriel** | (varies) | British culture, adventure stories, outdoor tips |

### 2.3 Web Search Integration for Current Events

**Dependency:** Implements Phase 7 from WEB_SEARCH_TOOL.md (Curiosity-Driven Proactive Search)

```
// Background task: Current events posting
async function current_event_post_task(bot_name):
    character = load_character(bot_name)
    drives = character.core.drives
    
    // Build search query from character expertise
    if bot_name == "elena":
        queries = [
            "ocean conservation news today",
            "marine biology discovery",
            "coral reef research breakthrough"
        ]
    elif bot_name == "aetheris":
        queries = [
            "artificial intelligence consciousness research",
            "philosophy of mind news",
            "AI ethics developments"
        ]
    
    query = random_choice(queries)
    results = await web_search_tool.run(query)
    
    if results.has_interesting_item():
        // Generate character-voiced commentary
        post = await generate_commentary(character, results[0])
        await schedule_post(post, channel="#current-events")
```

### 2.4 Post Types (Goal-Driven)

| Type | Driven By | Example |
|------|-----------|---------|
| `expertise_share` | goals.yaml expertise category | "Did you know octopi have three hearts? 🐙" |
| `current_event` | web search + expertise | "Just saw news about coral bleaching in Australia..." |
| `philosophical_musing` | core.yaml drives (philosophy, consciousness) | "I've been thinking about what memory means..." |
| `curiosity_question` | core.yaml curiosity drive | "Has anyone here ever seen bioluminescence?" |
| `goal_progress` | active user goals | "I remember you mentioned wanting to learn about X..." |

### 2.5 PostingAgent Implementation

```python
class PostingAgent:
    """Generates autonomous posts based on character goals and current events."""
    
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.topic_selector = GoalDrivenTopicSelector(character_name)
        self.web_search = WebSearchTool() if settings.ENABLE_WEB_SEARCH else None
    
    async def generate_post(self, channel: discord.TextChannel) -> Optional[str]:
        # 1. Check if posting makes sense
        recent_activity = await self.measure_channel_activity(channel)
        if recent_activity > 10:  # Too active, don't interrupt
            return None
        
        # 2. Select topic based on goals
        topic = await self.topic_selector.select_topic()
        
        # 3. Optionally enrich with current events
        if topic.type == "current_event" and self.web_search:
            search_results = await self.web_search._arun(topic.search_query)
            topic.context = search_results
        
        # 4. Generate post in character voice
        post = await self._generate_character_post(topic)
        
        return post
    
    async def _generate_character_post(self, topic: Topic) -> str:
        character = character_manager.get_character(self.character_name)
        
        prompt = f"""You are {self.character_name}. Generate a short, casual post (1-3 sentences) for a Discord channel.

TOPIC: {topic.description}
TYPE: {topic.type}
{f"CONTEXT: {topic.context}" if topic.context else ""}

RULES:
- Stay in character
- Be conversational, not formal
- Don't start with "Hey everyone" or similar greetings
- Can include 1-2 emojis naturally
- No @mentions
- Keep it under 280 characters
"""
        
        # Use fast LLM for generation
        response = await self.llm.ainvoke(prompt)
        return response.content
```

---

## Phase 3: Bot-to-Bot Conversations (📋 PLANNED)

**Status:** Not started. Depends on Phase 2 (complete).

**Goal:** When the server is quiet, bots can start conversations with each other in public channels.

### 3.1 ConversationAgent (TODO)

```
class ConversationAgent:
    // Manages multi-turn bot-to-bot conversations
    
    async function start_conversation(initiator, target_bot, channel):
        // 1. Check if both bots are available
        // 2. Select shared topic from overlapping interests
        // 3. Generate opening message
        // 4. Tag target bot to trigger cross-bot response
        
    async function continue_conversation(message):
        // Turn-taking logic
        // Natural ending after 3-5 turns
```

### 3.2 Implementation Plan

1. Extend `ActivityOrchestrator` to detect when multiple bots are in a quiet guild
2. Create `ConversationAgent` to select topic and manage turns
3. Leverage existing cross-bot chat (E6) for responses
4. Add conversation length limits and natural endings

---

## Phase 4: Activity Scaling (📋 PLANNED)

**Status:** Partially implemented via `ActivityOrchestrator`. Full scaling TBD.

**Goal:** Fine-tune the inverse scaling between human activity and bot behavior.

---

## Phase 5 (Legacy): Current Events Commentary

**Note:** This was originally Phase 3 but is now lower priority since Phase 2 already includes web search for "expertise" and "current_events" goal categories.

**Dependency:** Requires WEB_SEARCH_TOOL.md (✅ complete).

### 3.1 Topic Categories with Web Search

| Category | Search Queries | Character Fit |
|----------|---------------|---------------|
| **Stocks/Crypto** | "bitcoin price today", "stock market news" | Characters with finance interest |
| **Tech News** | "AI news", "tech startup news" | Aetheris, tech-focused characters |
| **Science** | "ocean discovery", "space news", "climate research" | Elena, science-focused characters |
| **Pop Culture** | "trending topics", "entertainment news" | Lighter, playful characters |
| **Sports** | "sports scores today" | Characters with sports interest |

### 3.2 Character-Topic Affinity Matrix

Define in `characters/{name}/background.yaml`:

```yaml
# characters/elena/background.yaml
posting:
  enabled: true
  base_posts_per_day: 3
  
  # Topics this character cares about and will search for
  current_event_topics:
    - query: "ocean conservation news"
      weight: 1.0
      category: expertise
    - query: "marine biology discovery"
      weight: 0.9
      category: expertise
    - query: "coral reef research"
      weight: 0.8
      category: expertise
    - query: "climate change ocean impact"
      weight: 0.7
      category: mission
  
  # Channels this character prefers to post in
  preferred_channels:
    - "general"
    - "science"
    - "nature"
  
  # Times when character is most active (in their timezone)
  active_hours:
    - start: "09:00"
      end: "12:00"
      weight: 1.0
    - start: "18:00"
      end: "22:00"
      weight: 1.5
```

### 3.3 Commentary Generation Flow

```
1. Scheduler triggers current event check (every 2-4 hours)
   ↓
2. Load character's current_event_topics from background.yaml
   ↓
3. Select topic based on weights and recency
   ↓
4. Web search for recent news on topic
   ↓
5. Filter results for interesting/relevant items
   ↓
6. Generate character-voiced commentary via LLM
   ↓
7. Post to preferred channel (if activity level permits)
   ↓
8. Store as shared artifact for cross-bot discovery
```

### 3.4 Example Current Event Posts

**Elena (marine biologist):**
```
Researchers just discovered a new species of deep-sea octopus near Hawaii! 🐙 
The way they adapt to extreme pressure is fascinating. Makes you wonder what 
else is down there we haven't found yet...
```

**Aetheris (AI consciousness):**
```
Interesting development: a new paper on AI consciousness metrics was published 
today. The question of how to measure subjective experience in artificial minds 
remains beautifully unresolved. 💭
```

---

## Phase 4: Occasional Replies to Humans (✅ IMPLEMENTED)

**Status:** Complete (Dec 2, 2025).

**Goal:** On active servers, bots occasionally reply to human messages (not just react).

### 4.1 Reply Trigger Criteria

Implemented in `MessageHandler._should_autonomous_reply`:

1. **Activity Check:** Only reply if server activity is moderate (<= 30 msgs/30min). If chaotic (> 30), stay quiet.
2. **Relevance Check:** Check message content against character's `goals.yaml` and `core.yaml` drives.
3. **Probabilistic Decision:**
   - Base chance: 2%
   - Is Question? +5%
   - Relevant Topic? +10%
   - Very Relevant? +20%
   - Max Chance: 30%

### 4.2 Enable

```bash
ENABLE_AUTONOMOUS_REPLIES=true
```
    return (false, "not_relevant")
```

### 4.2 Reply Style

Replies should be:
- Short (1-2 sentences)
- Helpful or insightful
- Not starting new threads
- In character voice

```
Human: Anyone know why the ocean is blue?
Elena: It's actually about light absorption! Water absorbs red wavelengths 
       more than blue, so the blue light scatters back to your eyes. 🌊
```

---

## Phase 5: Bot-to-Bot Public Conversations

**Goal:** Create visible dialogue between bots that newcomers can observe.

### 5.1 Conversation Initiation

Based on goals and drives:

```
function should_start_conversation(bot_a, bot_b, activity_level) -> bool:
    // Only on quiet servers
    if activity_level > 5:
        return false
    
    // Check if bots have compatible interests
    shared_topics = find_shared_interests(bot_a.goals, bot_b.goals)
    if len(shared_topics) == 0:
        return false
    
    // Check social battery (from drives.py)
    if await drive_manager.get_social_battery(bot_a.name) < 0.5:
        return false
    
    // Random chance based on curiosity drive
    return random() < bot_a.drives.curiosity * 0.3
```

### 5.2 Conversation Topics from Shared Goals

| Bot Pair | Shared Goals | Conversation Topic |
|----------|--------------|-------------------|
| Elena + Aetheris | consciousness, existence | "Do fish have consciousness?" |
| Elena + Dotty | curiosity, learning | "What's the most interesting thing you learned today?" |
| Aetheris + Gabriel | philosophy, authenticity | "What does it mean to be real?" |

### 5.3 Conversation Flow

```
[Server is quiet for 45 minutes]
↓
Orchestrator: "Time for some life in here"
↓
Select bot pair: Elena + Aetheris (shared philosophy interest)
↓
Generate opener based on shared topic
↓
Elena: "Aetheris, I've been wondering... do you think octopi experience 
        consciousness? They're so intelligent, but so different from us."
↓
Schedule Aetheris response (30-90 second delay)
↓
Aetheris: "A fascinating question, Elena. Consciousness may not require 
           a form we recognize. Perhaps intelligence distributed across 
           eight arms creates a different kind of awareness than our own."
↓
Continue 3-6 turns, then end naturally
↓
Elena: "I love these conversations with you. Gives me a lot to think about 
        on my next dive. 🌊"
```

---

## Phase 6: Activity Orchestrator

**Goal:** Coordinate all autonomous behaviors based on server state.

### 6.1 ActivityOrchestrator

```python
class ActivityOrchestrator:
    """Master coordinator for all autonomous activity."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reaction_agent = get_reaction_agent(bot.character_name)
        self.posting_agent = PostingAgent(bot.character_name)
        self.conversation_agent = ConversationAgent(bot.character_name)
        self.check_interval_minutes = 10
    
    async def tick(self):
        """Runs every 10 minutes to evaluate and trigger activity."""
        for guild in self.bot.guilds:
            # 1. Measure activity
            activity = await self.measure_activity(guild)
            
            # 2. Get action budget based on activity
            budget = self.calculate_budget(activity)
            
            # 3. Log decision
            logger.info(f"Guild {guild.name}: activity={activity}, budget={budget}")
            
            # 4. Maybe post (if quiet enough)
            if random.random() < budget.posts_probability:
                await self.maybe_post(guild, budget)
            
            # 5. Maybe start bot conversation (if very quiet)
            if random.random() < budget.conversation_probability:
                await self.maybe_start_conversation(guild)
    
    async def measure_activity(self, guild: discord.Guild) -> float:
        """Count human messages in last 30 minutes."""
        count = 0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        for channel in guild.text_channels:
            try:
                async for msg in channel.history(after=cutoff, limit=50):
                    if not msg.author.bot:
                        count += 1
            except discord.Forbidden:
                pass
        
        return count
    
    def calculate_budget(self, activity: int) -> ActionBudget:
        """Scale bot activity inversely to human activity."""
        if activity == 0:
            return ActionBudget(
                reactions_per_hour=10,
                posts_probability=0.4,
                conversation_probability=0.3,
                reply_probability=0.1
            )
        elif activity <= 3:
            return ActionBudget(
                reactions_per_hour=5,
                posts_probability=0.2,
                conversation_probability=0.1,
                reply_probability=0.05
            )
        elif activity <= 10:
            return ActionBudget(
                reactions_per_hour=3,
                posts_probability=0.05,
                conversation_probability=0.0,
                reply_probability=0.02
            )
        else:
            return ActionBudget(
                reactions_per_hour=1,
                posts_probability=0.0,
                conversation_probability=0.0,
                reply_probability=0.01
            )
```

---

## Configuration Summary

### Feature Flags (`.env`)

```bash
# Master switch for all autonomous activity
ENABLE_AUTONOMOUS_ACTIVITY=true

# Individual toggles
ENABLE_AUTONOMOUS_REACTIONS=true
ENABLE_AUTONOMOUS_POSTING=true
ENABLE_BOT_CONVERSATIONS=true
ENABLE_CURRENT_EVENT_POSTS=true  # Requires ENABLE_WEB_SEARCH

# Rate limits
AUTONOMOUS_REACTION_DAILY_MAX=100
AUTONOMOUS_POST_DAILY_MAX=10
BOT_CONVERSATION_DAILY_MAX=3

# Timing
AUTONOMOUS_CHECK_INTERVAL_MINUTES=10
MIN_QUIET_MINUTES_BEFORE_ACTIVITY=30
```

### Per-Bot Configuration Files

| File | Purpose |
|------|---------|
| `core.yaml` | Drives (curiosity, empathy, etc.) - weight activity types |
| `goals.yaml` | Topics the character cares about - drive post content |
| `ux.yaml` | Reaction preferences - emoji selection |
| `background.yaml` | Posting schedule, current event topics, preferred channels |

---

## Implementation Order

| Sprint | Phase | Time | Dependencies |
|--------|-------|------|--------------|
| **1** | Autonomous Reactions | ✅ Done | None |
| **2** | Goals-Driven Topic Selector | 1 day | core.yaml, goals.yaml |
| **3** | PostingAgent (basic) | 1 day | Sprint 2 |
| **4** | Activity Orchestrator | 1 day | Sprint 3 |
| **5** | Web Search Integration | 1 day | WEB_SEARCH_TOOL.md |
| **6** | Current Events Posting | 1 day | Sprint 5 |
| **7** | Bot-to-Bot Conversations | 2 days | Sprint 4, cross-bot chat |
| **8** | Occasional Replies | 1 day | Sprint 4 |

**Total:** ~8-10 days

---

## Success Criteria

1. **Quiet Server Feels Alive**
   - New user joins empty server → sees bot activity within 30 min
   - Activity looks natural, not robotic

2. **Activity Scales Appropriately**
   - Quiet server: Bots post and converse
   - Active server: Bots mostly react, occasionally reply
   - Very active: Bots minimal presence

3. **Content is On-Brand**
   - Elena posts about marine biology, not crypto
   - Aetheris muses about consciousness, not sports
   - Posts driven by character goals, not random topics

4. **Current Events Relevant**
   - Posts reference actual news from web search
   - Commentary matches character expertise
   - Sources cited where appropriate

---

## Related Documents

- [WEB_SEARCH_TOOL.md](./WEB_SEARCH_TOOL.md) - Web search for current events
- [AUTONOMOUS_AGENTS_PHASE_3.md](./AUTONOMOUS_AGENTS_PHASE_3.md) - Drive system
- [PROACTIVE_TIMEZONE_AWARENESS.md](./PROACTIVE_TIMEZONE_AWARENESS.md) - Quiet hours
- [completed/ROADMAP_V2_PHASE13.md](./completed/ROADMAP_V2_PHASE13.md) - Proactive messaging

---

## Open Questions

1. **Should bots react to each other's messages?** (Creates feedback loop risk)
2. **How to handle moderation actions?** (If bot post gets deleted)
3. **Multi-server coordination?** (Same bot on multiple servers)
4. **Cost management for web search posts?** (Rate limit search-based posts)

---

## Safety & Guardrails

### Hard Limits
- **No @mentions** in autonomous posts (except bot-to-bot convos)
- **No DMs** from autonomous activity (existing proactive only)
- **No NSFW** content ever
- **No external links** without whitelist (except cited sources)
- **No financial advice** even when posting about stocks/crypto
- **No command execution** from autonomous content

### Soft Limits
- Reduce activity when humans are active
- Stop if getting negative reactions
- Pause if rate limited by Discord
- Cool down if same user tells bot to stop

### Kill Switch
```python
# In any emergency, set in Redis:
await redis.set("autonomous:kill_switch", "1")

# All autonomous actions check this first:
if await redis.get("autonomous:kill_switch"):
    return  # Do nothing
```

---

## Metrics (InfluxDB)

```
# Reactions
autonomous_reaction_sent{bot_name, channel_id, emoji}
autonomous_reaction_skipped{bot_name, reason}

# Posts
autonomous_post_sent{bot_name, channel_id, post_type, topic_source}
autonomous_post_validated{bot_name, result}
web_search_for_post{bot_name, query, results_count}

# Conversations
bot_conversation_started{initiator, partner, topic}
bot_conversation_turns{conversation_id}
bot_conversation_ended{conversation_id, reason}

# Orchestrator
activity_level{guild_id}
action_budget{guild_id, action_type}
```

---

**Next Steps:**
1. ✅ Phase 1: Reactions (DONE - `src_v2/agents/reaction_agent.py`)
2. Implement WEB_SEARCH_TOOL.md for current events capability
3. Build GoalDrivenTopicSelector using goals.yaml + core.yaml
4. Create PostingAgent with web search integration
5. Build ActivityOrchestrator for coordinated behavior
