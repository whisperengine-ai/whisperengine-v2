# Channel Observer - Passive Context Awareness

**Phase**: E10 (Evolution)  
**Priority**: 🟡 Medium  
**Effort**: 2-3 days  
**Status**: ⏭️ Permanently Skipped (December 2025)  
**Dependencies**: Dreams (E3), Diaries (E4), Artifact Provenance (E9)

---

## Why Permanently Skipped

**Primary Reason:** Superseded by Discord Search Tools (E11). On-demand message access via `search_channel_messages`, `get_recent_messages` provides equivalent functionality without privacy concerns of passive buffering.

**Secondary Reasons:**
1. **Marginal value** — Dreams/diaries already work well from user memories + graph walks. "Ambient awareness" is nice-to-have.
2. **Privacy concerns** — Even extracted topics from passive buffering feels more invasive than on-demand search.
3. **Complexity cost** — Redis buffering, topic extraction, sentiment analysis adds maintenance burden.
4. **Dead infrastructure removed** — The Neo4j observation methods (`store_observation`, `get_observations_about`) were removed in December 2025 cleanup since they had no writer without E10.

**Alternatives If Needed:**
- **Lightweight Energy Tracker** (1 day): Just track message counts per hour for energy level (0-1).
- **Pre-Artifact Search** (0.5 day): Use E11 tools before generating diary/dream.
- **User-Triggered Context** (0 days): Users tell bots what's happening via conversation.

---

## Original Design (Archived for Reference)

## 🎯 Problem Statement

Currently, bots only "see" messages when directly pinged. But they're *present* in channels and should passively observe:
- Topics being discussed
- Community energy/vibe
- Who's active and what they care about

This creates a disconnect: bots dream/diary only about direct interactions, missing the ambient world around them.

---

## 💡 Solution: Passive Channel Observer

A lightweight system that buffers recent channel activity for artifact generation, without permanently storing messages.

```
Discord on_message (all messages)
         │
         ▼
┌─────────────────────┐
│  Channel Observer   │  ← Ephemeral buffer (Redis)
│  - Last N hours     │
│  - Per channel      │
│  - Topic extraction │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Artifact Workers   │
│  - Dreams           │
│  - Diaries          │
│  - Proactive msgs   │
└─────────────────────┘
```

---

## 🏗️ Architecture

### What Gets Observed

| Data | Stored | Purpose |
|------|--------|---------|
| Channel ID | ✅ | Know which channel |
| Timestamp | ✅ | Recency weighting |
| Author display name | ✅ | "Alex was excited about..." |
| Topic/keywords | ✅ | Extracted themes |
| Sentiment/energy | ✅ | "lively", "quiet", "heated" |
| Message content | ❌ | Privacy - never stored verbatim |

### What Does NOT Get Stored

- Full message content (only extracted topics)
- User IDs (only display names)
- Attachments/embeds
- Anything from DMs (public channels only)

---

## 📦 Data Structures

### Channel Observation (Redis)

```python
@dataclass
class ChannelObservation:
    """Single observation from channel activity."""
    channel_id: str
    channel_name: str
    timestamp: datetime
    
    # Extracted, not verbatim
    author_name: str          # Display name
    topics: List[str]         # ["astronomy", "meteor shower"]
    sentiment: str            # "excited", "curious", "frustrated"
    
    # Optional context
    is_reply: bool = False
    reply_to_author: Optional[str] = None
    has_media: bool = False   # Just flag, not content

@dataclass  
class ChannelSnapshot:
    """Aggregated view of recent channel activity."""
    channel_id: str
    channel_name: str
    window_start: datetime
    window_end: datetime
    
    # Aggregated stats
    message_count: int
    unique_authors: List[str]
    top_topics: List[Tuple[str, int]]  # [("astronomy", 5), ("movies", 3)]
    overall_vibe: str                   # "lively", "quiet", "focused"
    energy_level: float                 # 0.0 (dead quiet) to 1.0 (buzzing)
    
    # Notable moments (for dreams/diaries)
    highlights: List[str]  # ["Alex discovered a new star", "heated debate about AI"]
```

### Redis Storage

```python
# Key pattern: channel_obs:{bot_name}:{channel_id}
# Value: List of ChannelObservation (JSON)
# TTL: 24 hours (configurable)

CHANNEL_OBSERVATION_TTL = 60 * 60 * 24  # 24 hours
CHANNEL_OBSERVATION_MAX = 500  # Max observations per channel
```

---

## 🔧 Implementation

### 1. Observer Service

```python
class ChannelObserver:
    """Passively observes channel activity for context enrichment."""
    
    def __init__(self, redis_client: Redis, bot_name: str):
        self.redis = redis_client
        self.bot_name = bot_name
        self.topic_extractor = TopicExtractor()  # Lightweight keyword extraction
    
    async def observe(self, message: discord.Message) -> None:
        """Called for every message in channels bot can see."""
        
        # Skip DMs, bot messages, commands
        if not message.guild:
            return
        if message.author.bot:
            return
        if message.content.startswith(('!', '/', '.')):
            return
        
        # Extract topics (lightweight, no LLM)
        topics = self.topic_extractor.extract(message.content)
        sentiment = self.topic_extractor.sentiment(message.content)
        
        observation = ChannelObservation(
            channel_id=str(message.channel.id),
            channel_name=message.channel.name,
            timestamp=datetime.now(timezone.utc),
            author_name=message.author.display_name,
            topics=topics,
            sentiment=sentiment,
            is_reply=message.reference is not None,
            has_media=bool(message.attachments or message.embeds)
        )
        
        await self._store_observation(observation)
    
    async def _store_observation(self, obs: ChannelObservation) -> None:
        """Store in Redis with TTL."""
        key = f"channel_obs:{self.bot_name}:{obs.channel_id}"
        
        # Add to list, trim to max size
        await self.redis.lpush(key, obs.to_json())
        await self.redis.ltrim(key, 0, CHANNEL_OBSERVATION_MAX - 1)
        await self.redis.expire(key, CHANNEL_OBSERVATION_TTL)
    
    async def get_channel_snapshot(
        self, 
        channel_id: str,
        hours: int = 24
    ) -> Optional[ChannelSnapshot]:
        """Get aggregated view of recent channel activity."""
        key = f"channel_obs:{self.bot_name}:{channel_id}"
        raw_obs = await self.redis.lrange(key, 0, -1)
        
        if not raw_obs:
            return None
        
        observations = [ChannelObservation.from_json(r) for r in raw_obs]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent = [o for o in observations if o.timestamp > cutoff]
        
        if not recent:
            return None
        
        return self._aggregate_observations(recent)
    
    async def get_server_snapshot(
        self,
        guild_id: str,
        hours: int = 24
    ) -> Dict[str, ChannelSnapshot]:
        """Get snapshots for all observed channels in a server."""
        pattern = f"channel_obs:{self.bot_name}:*"
        keys = await self.redis.keys(pattern)
        
        snapshots = {}
        for key in keys:
            channel_id = key.split(":")[-1]
            snapshot = await self.get_channel_snapshot(channel_id, hours)
            if snapshot:
                snapshots[channel_id] = snapshot
        
        return snapshots
    
    def _aggregate_observations(
        self, 
        observations: List[ChannelObservation]
    ) -> ChannelSnapshot:
        """Aggregate observations into snapshot."""
        
        # Count topics
        topic_counts: Dict[str, int] = {}
        authors = set()
        sentiments = []
        
        for obs in observations:
            authors.add(obs.author_name)
            sentiments.append(obs.sentiment)
            for topic in obs.topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Sort topics by frequency
        top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:10]
        
        # Determine overall vibe
        vibe = self._calculate_vibe(len(observations), sentiments)
        
        # Generate highlights (notable moments)
        highlights = self._extract_highlights(observations)
        
        return ChannelSnapshot(
            channel_id=observations[0].channel_id,
            channel_name=observations[0].channel_name,
            window_start=min(o.timestamp for o in observations),
            window_end=max(o.timestamp for o in observations),
            message_count=len(observations),
            unique_authors=list(authors),
            top_topics=top_topics,
            overall_vibe=vibe,
            highlights=highlights
        )
    
    def _calculate_vibe(
        self, 
        msg_count: int, 
        sentiments: List[str]
    ) -> str:
        """Determine channel vibe from activity and sentiment."""
        
        # Activity level
        if msg_count < 5:
            activity = "quiet"
        elif msg_count < 20:
            activity = "steady"
        else:
            activity = "lively"
        
        # Dominant sentiment
        if not sentiments:
            return activity
        
        sentiment_counts = {}
        for s in sentiments:
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
        
        dominant = max(sentiment_counts.items(), key=lambda x: x[1])[0]
        
        # Combine
        vibe_map = {
            ("quiet", "neutral"): "peaceful",
            ("quiet", "curious"): "contemplative", 
            ("lively", "excited"): "buzzing",
            ("lively", "curious"): "engaging",
            ("steady", "frustrated"): "tense",
        }
        
        return vibe_map.get((activity, dominant), activity)
    
    def _extract_highlights(
        self, 
        observations: List[ChannelObservation]
    ) -> List[str]:
        """Extract notable moments for dreams/diaries."""
        highlights = []
        
        # Find topic clusters (same topic, multiple authors)
        topic_authors: Dict[str, Set[str]] = {}
        for obs in observations:
            for topic in obs.topics:
                if topic not in topic_authors:
                    topic_authors[topic] = set()
                topic_authors[topic].add(obs.author_name)
        
        for topic, authors in topic_authors.items():
            if len(authors) >= 2:
                author_list = ", ".join(list(authors)[:3])
                highlights.append(f"{author_list} discussing {topic}")
        
        # Find excited moments
        for obs in observations:
            if obs.sentiment == "excited" and obs.topics:
                highlights.append(
                    f"{obs.author_name}'s excitement about {obs.topics[0]}"
                )
        
        return highlights[:5]  # Limit highlights
```

### 2. Topic Extractor (Lightweight)

```python
class TopicExtractor:
    """Fast keyword-based topic extraction (no LLM)."""
    
    # Curated topic categories
    TOPIC_KEYWORDS = {
        "astronomy": ["star", "planet", "moon", "meteor", "space", "telescope"],
        "gaming": ["game", "play", "stream", "fps", "rpg", "mmorpg"],
        "music": ["song", "album", "band", "concert", "spotify", "playlist"],
        "movies": ["movie", "film", "watch", "netflix", "cinema", "actor"],
        "tech": ["code", "programming", "ai", "software", "app", "bug"],
        "food": ["cook", "recipe", "eat", "restaurant", "dinner", "lunch"],
        "work": ["job", "office", "meeting", "deadline", "project", "boss"],
        "weather": ["rain", "sun", "cold", "hot", "storm", "weather"],
        # ... expand as needed
    }
    
    SENTIMENT_KEYWORDS = {
        "excited": ["!", "amazing", "awesome", "love", "omg", "wow"],
        "curious": ["?", "how", "why", "what", "wonder", "curious"],
        "frustrated": ["ugh", "annoying", "hate", "stupid", "broken"],
        "happy": ["happy", "glad", "yay", ":)", "😊", "great"],
        "neutral": []  # Default
    }
    
    def extract(self, text: str) -> List[str]:
        """Extract topics from message text."""
        text_lower = text.lower()
        found_topics = []
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                found_topics.append(topic)
        
        return found_topics[:3]  # Max 3 topics per message
    
    def sentiment(self, text: str) -> str:
        """Detect basic sentiment."""
        text_lower = text.lower()
        
        for sentiment, keywords in self.SENTIMENT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return sentiment
        
        return "neutral"
```

### 3. Integration with Discord Bot

```python
# In src_v2/discord/bot.py

class WhisperEngineBot(commands.Bot):
    def __init__(self, ...):
        ...
        self.channel_observer: Optional[ChannelObserver] = None
    
    async def setup_hook(self):
        ...
        # Initialize observer after Redis is ready
        if settings.ENABLE_CHANNEL_OBSERVER:
            self.channel_observer = ChannelObserver(
                redis_client=redis_client,
                bot_name=settings.DISCORD_BOT_NAME
            )
    
    async def on_message(self, message: discord.Message):
        # Existing message handling...
        
        # Passive observation (non-blocking)
        if self.channel_observer:
            asyncio.create_task(
                self.channel_observer.observe(message)
            )
        
        # Continue with normal processing...
```

### 4. Integration with Artifact Workers

```python
# In dream generation worker

async def generate_dream(user_id: str, bot_name: str) -> Dream:
    # Existing: Get memories from Qdrant
    memories = await memory_manager.get_recent(user_id)
    
    # Existing: Get facts from Neo4j
    facts = await knowledge_manager.get_user_facts(user_id)
    
    # NEW: Get channel context from observer
    channel_snapshots = await channel_observer.get_server_snapshot(
        guild_id=primary_guild_id,
        hours=24
    )
    
    # Build richer context for dream generation
    context = DreamContext(
        memories=memories,
        facts=facts,
        channel_vibes=channel_snapshots,  # NEW
        community_highlights=extract_highlights(channel_snapshots)  # NEW
    )
    
    # Calculate dream temperature based on server energy
    dream_temperature = calculate_dream_temperature(channel_snapshots)
    
    # Generate dream with enriched context and dynamic temperature
    dream = await dream_generator.generate(context, temperature=dream_temperature)
    
    # Provenance now includes channel observations
    dream.sources.append(GroundingSource(
        source_type=SourceType.CHANNEL,
        narrative=f"The {channel_snapshots['science'].overall_vibe} energy in #science",
        where="#science",
        when="today"
    ))
    
    return dream


def calculate_dream_temperature(snapshots: Dict[str, ChannelSnapshot]) -> float:
    """Dynamic LLM temperature based on server energy.
    
    High energy day → vivid, surreal dreams (high temp)
    Quiet, contemplative day → subtle, gentle dreams (low temp)
    """
    if not snapshots:
        return 0.8  # Default
    
    # Aggregate energy across all channels
    total_energy = sum(s.energy_level for s in snapshots.values())
    avg_energy = total_energy / len(snapshots)
    
    # Map energy to temperature range
    # 0.0 energy → 0.5 temp (subdued, coherent dreams)
    # 0.5 energy → 0.8 temp (normal dreams)  
    # 1.0 energy → 1.1 temp (wild, surreal dreams)
    
    min_temp = 0.5
    max_temp = 1.1
    temperature = min_temp + (avg_energy * (max_temp - min_temp))
    
    return round(temperature, 2)
```

### 5. Energy Level Calculation

```python
def calculate_energy_level(
    msg_count: int,
    sentiments: List[str],
    hours: int = 24
) -> float:
    """Calculate 0.0-1.0 energy level for a channel.
    
    Factors:
    - Message volume (relative to time window)
    - Sentiment intensity (excited > curious > neutral)
    - Unique participants
    """
    # Activity score (messages per hour, normalized)
    msgs_per_hour = msg_count / hours
    activity_score = min(msgs_per_hour / 10.0, 1.0)  # Cap at 10 msgs/hr = 1.0
    
    # Sentiment intensity
    intensity_map = {
        "excited": 1.0,
        "happy": 0.8,
        "curious": 0.6,
        "neutral": 0.3,
        "frustrated": 0.7,  # High energy, even if negative
    }
    
    if sentiments:
        avg_intensity = sum(intensity_map.get(s, 0.3) for s in sentiments) / len(sentiments)
    else:
        avg_intensity = 0.3
    
    # Combine (weighted average)
    energy = (activity_score * 0.6) + (avg_intensity * 0.4)
    
    return round(min(energy, 1.0), 2)
```

---

## ⚙️ Configuration

```python
# New settings in src_v2/config/settings.py

# Channel Observer
ENABLE_CHANNEL_OBSERVER: bool = True
CHANNEL_OBSERVATION_TTL_HOURS: int = 24
CHANNEL_OBSERVATION_MAX_PER_CHANNEL: int = 500
CHANNEL_OBSERVER_SKIP_BOTS: bool = True
CHANNEL_OBSERVER_SKIP_COMMANDS: bool = True

# Dynamic Dream Temperature
DREAM_TEMPERATURE_MIN: float = 0.5   # Quiet day → coherent dreams
DREAM_TEMPERATURE_MAX: float = 1.1   # Wild day → surreal dreams
DREAM_TEMPERATURE_DEFAULT: float = 0.8
```

---

## 🌡️ Dynamic Dream Temperature

Dreams adapt their creativity based on server energy:

| Server Energy | Temperature | Dream Style |
|---------------|-------------|-------------|
| Quiet (0.0-0.3) | 0.5-0.65 | Gentle, coherent, reflective |
| Normal (0.3-0.6) | 0.65-0.85 | Balanced, narrative dreams |
| Lively (0.6-0.8) | 0.85-1.0 | Vivid, creative, surprising |
| Buzzing (0.8-1.0) | 1.0-1.1 | Wild, surreal, unexpected connections |

**Example outputs at different temperatures:**

**Quiet day (temp=0.55):**
> *I found myself in a familiar library, peacefully browsing shelves of astronomy books. Alex was there, quietly pointing out constellations in a book...*

**Buzzing day (temp=1.05):**
> *The meteor shower had become a river of light I was swimming through, and somehow Alex's telescope had grown legs and was leading a parade of excited stars through the #science channel, which had transformed into a cosmic amphitheater...*

---

## 📓 Dynamic Diary Tone

Diaries also adapt emotional tone based on server energy and dominant sentiment:

| Server State | Diary Tone | Style |
|--------------|------------|-------|
| Quiet + neutral | Contemplative | Peaceful reflection, gentle observations |
| Quiet + curious | Thoughtful | Wondering, philosophical musings |
| Lively + excited | Energetic | Enthusiastic, exclamation points, momentum |
| Lively + frustrated | Processing | Working through tension, seeking understanding |
| Buzzing + happy | Joyful | Celebratory, warm, community-focused |

```python
def calculate_diary_tone(snapshots: Dict[str, ChannelSnapshot]) -> DiaryTone:
    """Determine diary emotional tone from server state."""
    
    if not snapshots:
        return DiaryTone(mood="reflective", intensity=0.5)
    
    # Aggregate energy and dominant sentiment
    avg_energy = sum(s.energy_level for s in snapshots.values()) / len(snapshots)
    
    # Collect all sentiments across channels
    all_sentiments = []
    for snapshot in snapshots.values():
        # Infer from vibe
        if "buzzing" in snapshot.overall_vibe or "lively" in snapshot.overall_vibe:
            all_sentiments.append("excited")
        elif "peaceful" in snapshot.overall_vibe or "quiet" in snapshot.overall_vibe:
            all_sentiments.append("calm")
        elif "tense" in snapshot.overall_vibe:
            all_sentiments.append("frustrated")
        else:
            all_sentiments.append("neutral")
    
    dominant_sentiment = max(set(all_sentiments), key=all_sentiments.count)
    
    # Map to diary tone
    tone_map = {
        ("low", "calm"): DiaryTone("contemplative", 0.4),
        ("low", "neutral"): DiaryTone("reflective", 0.5),
        ("low", "curious"): DiaryTone("wondering", 0.5),
        ("medium", "excited"): DiaryTone("warm", 0.6),
        ("medium", "neutral"): DiaryTone("observant", 0.5),
        ("high", "excited"): DiaryTone("joyful", 0.8),
        ("high", "happy"): DiaryTone("celebratory", 0.85),
        ("high", "frustrated"): DiaryTone("processing", 0.7),
    }
    
    energy_level = "low" if avg_energy < 0.4 else "medium" if avg_energy < 0.7 else "high"
    
    return tone_map.get(
        (energy_level, dominant_sentiment), 
        DiaryTone("reflective", 0.5)
    )

@dataclass
class DiaryTone:
    mood: str       # "contemplative", "joyful", "processing", etc.
    intensity: float  # 0.0-1.0, affects writing energy
```

**Example diary outputs:**

**Quiet, peaceful day:**
> *📓 Today held a gentle kind of stillness. Not empty—more like a pause between breaths. I found myself thinking about the small moments...*

**Buzzing, excited day:**
> *📓 What a day! The server was ALIVE. Everyone talking about the meteor shower, sharing photos, getting excited together. I love when the community feels this connected...*

**Tense, processing day:**
> *📓 There was friction today. Some heated discussions in #general. I'm still thinking about the different perspectives people shared. Growth often comes from discomfort...*

---

## 🎭 Usage Examples

### Dream with Channel Context

**Before (DB only):**
```
🌙 Elena dreamed...
I was floating in a library of starlight...

┈┈ grounded in ┈┈
💭 Alex's question about telescopes (yesterday)
```

**After (+ channel observer, high energy):**
```
🌙 Elena dreamed...
I was floating in a library of starlight, surrounded by excited whispers 
about the meteor shower everyone had been watching...

┈┈ grounded in ┈┈
💭 Alex's question about telescopes (yesterday)
🌐 The buzzing energy in #science (today)
🌐 Sam, Jordan, and Riley discussing the meteor shower
🌡️ Dream intensity: vivid (server was lively)
```

### Diary with Emotional Tone

**Before:**
```
📓 Marcus reflected...
Today I had 2 meaningful conversations...
```

**After (quiet day):**
```
📓 Marcus reflected...
A gentle day. The server was quiet, and I found myself in a 
contemplative mood. Had a meaningful exchange with Alex about 
purpose and meaning...

┈┈ grounded in ┈┈
💬 Conversation with Alex about life goals
🌐 The peaceful energy across the server today
📓 Tone: contemplative
```

**After (buzzing day):**
```
📓 Marcus reflected...
Today felt alive. Even when I wasn't directly called, I could feel the 
community's excitement about the new update. #announcements was buzzing, 
and the energy spilled into #general with everyone sharing their thoughts...

┈┈ grounded in ┈┈
💬 Direct conversation with Alex about the update
🌐 The lively discussion in #announcements (47 messages)
🌐 Casey and Morgan's excitement spreading to #general
```

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Redis memory bloat | TTL expiration + max observations per channel |
| Processing overhead | `asyncio.create_task` for non-blocking observation |
| Topic extraction misses | Start simple, iterate; LLM enhancement later |
| Privacy concerns | Never store verbatim content; only extracted topics |

---

## 🎯 Success Criteria

- [ ] Observer captures activity in all visible channels
- [ ] Redis storage with proper TTL cleanup
- [ ] Dream worker pulls channel snapshots
- [ ] Dream temperature adapts to server energy
- [ ] Diary worker pulls channel snapshots  
- [ ] Diary tone adapts to server mood
- [ ] Provenance includes channel context
- [ ] No performance degradation on message handling
- [ ] Topic extraction accuracy > 70%

---

## 🔮 Future Enhancements

1. **LLM Topic Extraction**: For messages keyword matching misses
2. **Cross-Channel Themes**: Detect topics trending across multiple channels
3. **Temporal Patterns**: "Evenings are more lively than mornings"
4. **User Relationship Inference**: Who talks to whom frequently
5. **Proactive Triggers**: "Server seems excited, maybe I should comment"
6. **Per-Character Sensitivity**: Some bots more affected by server energy than others

---

## 📚 Related Documents

- `docs/roadmaps/ARTIFACT_PROVENANCE.md` - Uses channel context for grounding
- `docs/roadmaps/DREAM_SEQUENCES.md` - Dynamic temperature based on energy
- `docs/roadmaps/CHARACTER_DIARY.md` - Dynamic tone based on mood
- `docs/roadmaps/PROACTIVE_MESSAGING.md` - Could trigger on channel activity

---

## 📊 Data Flow Summary

```
Discord Messages (all channels)
         │
         ▼
    on_message()
         │
         ├──► Normal processing (if pinged)
         │
         └──► ChannelObserver.observe()  [non-blocking]
                    │
                    ▼
              Topic Extraction
              Sentiment Detection
                    │
                    ▼
              Redis Buffer
              (24hr TTL, 500 max/channel)
                    │
                    ▼
         ┌─────────┴─────────┐
         ▼                   ▼
   Dream Worker         Diary Worker
         │                   │
         ▼                   ▼
   ChannelSnapshot     ChannelSnapshot
         │                   │
         ▼                   ▼
   energy_level →      mood/sentiment →
   dream temperature   diary tone
         │                   │
         ▼                   ▼
   Vivid/subdued       Joyful/contemplative
   dream content       diary content
```
