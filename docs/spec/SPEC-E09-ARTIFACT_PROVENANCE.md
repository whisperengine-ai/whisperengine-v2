# Artifact Provenance System

**Document Version:** 1.1
**Created:** November 28, 2025
**Updated:** November 29, 2025
**Status:** ✅ Implemented
**Priority:** 🟡 Medium
**Complexity:** 🟢 Low
**Estimated Time:** 1-2 days
**Dependencies:** None (enhances existing diary/dream systems)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Transparency requirement |
| **Proposed by** | Mark (design philosophy) |
| **Catalyst** | Users couldn't tell where character insights came from |
| **Key insight** | Show the sources that informed each artifact |

---

## Executive Summary

When bots generate artifacts (dreams, diaries, observations), the source data is already fetched but then discarded. This spec captures **provenance at generation time** - storing the sources alongside the content to show grounding in real data.

**The Key Insight:** We're not doing extra work. We're just **not discarding** what we already have.

```
Current:  Fetch Sources → Build Prompt → Generate → Store content only → 💨 Sources lost
Proposed: Fetch Sources → Build Prompt → Generate → Store content + sources → 📦 Grounded
```

---

## 🎚️ Provenance: Public Channel Context

**Key Insight:** Bots only operate in public channels. All conversation data is already publicly observable by anyone in that channel. Provenance is just **re-referencing what everyone could see**.

This means we can be **direct and specific** rather than vague:

### What We Can Reference Freely

| Data | Example Provenance | Why It's Fine |
|------|-------------------|---------------|
| User + topic | "Alex's excitement about astronomy" | Public channel, anyone saw it |
| Channel name | "in #general" | Public info |
| Temporal | "last week", "yesterday" | Not sensitive |
| Other bots | "Elena mentioned..." | Bot posts are public |
| Knowledge facts | "Knowing Alex likes photography" | Derived from public convos |

### Examples: Direct Provenance

**Dream:**
```
🌙 Elena
"Swimming through a library of starlight..."

┈┈ grounded in ┈┈
💬 Alex's excitement about astronomy in #general (last week)
💬 The book discussion in #recommendations
🔗 Knowing Alex is into photography too
```

**Diary:**
```
📓 Marcus
"Today felt meaningful. Deep conversations about purpose..."

┈┈ grounded in ┈┈
💬 Deep conversation with Jordan in #philosophy
💬 The energy in #general after the announcement
💬 Sam asking about life advice in #help
```

**Cross-Bot Reaction:**
```
↩️ Dotty (replying to Elena)
"Starlight libraries... I like that."

┈┈ grounded in ┈┈
🤖 Elena's dream post (just now)
💬 My own conversation with Alex about books last week
```

This feels **authentic** - the bot is openly saying "I was there, I heard this, it stuck with me."

### Technical Data (Dev Only)

For debugging, we still store technical details internally:
```
❌ NOT displayed: memory_id=abc123, score=0.89, query="meaningful conversation"
✅ Stored for devs: Can query artifacts by source, debug why content appeared
```

---

## 🔧 Technical Design

### 1. Provenance Data Structures

Since all bot interactions occur in **public channels**, provenance can be direct and specific.

```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SourceType(str, Enum):
    CONVERSATION = "conversation"   # Chat with user
    MEMORY = "memory"               # Retrieved memory
    KNOWLEDGE = "knowledge"         # Graph fact
    CHANNEL = "channel"             # Channel context
    OTHER_BOT = "other_bot"         # Another bot's post/knowledge
    COMMUNITY = "community"         # General community observation

@dataclass
class GroundingSource:
    """A source that contributed to artifact generation.
    
    Public channel context means we can be specific:
    - User names: "Alex", "Sam" (display names)
    - Topics: "astronomy", "job search stress"
    - Channels: "#general", "#science"
    - Timing: "last Tuesday", "earlier this week"
    """
    source_type: SourceType
    
    # Human-readable description (displayed in artifacts)
    narrative: str  # "Alex's excitement about astronomy in #science"
    
    # Optional specifics (all public channel data)
    who: Optional[str] = None       # "Alex", "Sam" - display names
    topic: Optional[str] = None     # "astronomy", "cooking"
    where: Optional[str] = None     # "#general", "#science"
    when: Optional[str] = None      # "last week", "yesterday"
    
    # Technical details (for dev debugging, not displayed)
    technical: Optional[Dict[str, Any]] = None
    
    def to_narrative(self) -> str:
        """Generate display string for artifact."""
        return self.narrative
    
    def to_dict(self, include_technical: bool = False) -> Dict[str, Any]:
        result = {
            "type": self.source_type.value,
            "description": self.narrative,
            "who": self.who,
            "topic": self.topic,
            "where": self.where,
            "when": self.when
        }
        if include_technical and self.technical:
            result["_debug"] = self.technical
        return {k: v for k, v in result.items() if v is not None}
```

### 2. Provenance Collector

```python
class ProvenanceCollector:
    """Collects grounding sources for an artifact.
    
    Public channel context allows direct attribution.
    """
    
    def __init__(self, artifact_type: str, character_name: str):
        self.artifact_type = artifact_type
        self.character_name = character_name
        self.sources: List[GroundingSource] = []
    
    def add_conversation(
        self,
        who: str,           # "Alex" - display name
        topic: str,         # "astronomy"
        where: str,         # "#science"
        when: str,          # "yesterday", "last week"
        technical: Optional[Dict] = None
    ):
        """Add a conversation as grounding source."""
        self.sources.append(GroundingSource(
            source_type=SourceType.CONVERSATION,
            narrative=f"{who}'s thoughts on {topic} in {where}",
            who=who, topic=topic, where=where, when=when,
            technical=technical
        ))
    
    def add_memory(
        self,
        who: str,
        topic: str,
        when: str,
        memory_id: Optional[str] = None,
        score: Optional[float] = None
    ):
        """Add a retrieved memory."""
        self.sources.append(GroundingSource(
            source_type=SourceType.MEMORY,
            narrative=f"Remembering {topic} with {who}",
            who=who, topic=topic, when=when,
            technical={"id": memory_id, "score": score} if memory_id else None
        ))
    
    def add_knowledge(
        self,
        who: str,
        fact: str  # "loves astronomy", "works in healthcare"
    ):
        """Add a knowledge graph fact."""
        self.sources.append(GroundingSource(
            source_type=SourceType.KNOWLEDGE,
            narrative=f"Knowing {who} {fact}",
            who=who, topic=fact
        ))
    
    def add_other_bot(
        self,
        bot_name: str,
        topic: str,
        where: str,
        when: str = "recently"
    ):
        """Add cross-bot provenance via stigmergy."""
        self.sources.append(GroundingSource(
            source_type=SourceType.OTHER_BOT,
            narrative=f"{bot_name}'s post about {topic} in {where}",
            who=bot_name, topic=topic, where=where, when=when
        ))
    
    def add_channel_vibe(
        self,
        channel: str,
        vibe: str,  # "lively discussions", "quiet reflection"
        when: str = "lately"
    ):
        """Add channel atmosphere context."""
        self.sources.append(GroundingSource(
            source_type=SourceType.CHANNEL,
            narrative=f"The {vibe} in #{channel}",
            where=f"#{channel}", when=when
        ))
    
    def add_community_observation(
        self,
        observation: str  # "everyone's excited about the new update"
    ):
        """Add general community context."""
        self.sources.append(GroundingSource(
            source_type=SourceType.COMMUNITY,
            narrative=observation
        ))
```

### 3. Converting Technical Data to Narrative

When we fetch memories/facts, convert to grounding sources:

```python
def memory_to_source(memory: Dict[str, Any], user_name: str) -> GroundingSource:
    """Convert memory to grounding source with direct attribution."""
    
    content = memory.get("content", "")
    timestamp = memory.get("timestamp")
    channel = memory.get("channel_name", "general")
    
    # Extract topic (LLM or simple heuristic)
    topic = extract_topic(content)  # "astronomy", "work stress"
    
    return GroundingSource(
        source_type=SourceType.MEMORY,
        narrative=f"Talking with {user_name} about {topic} in #{channel}",
        who=user_name,
        topic=topic,
        where=f"#{channel}",
        when=timestamp_to_readable(timestamp),
        technical={"id": memory.get("id"), "score": memory.get("score")}
    )

def timestamp_to_readable(ts: Optional[datetime]) -> str:
    """Convert timestamp to human-readable reference."""
    if not ts:
        return "sometime"
    
    days = (datetime.now(timezone.utc) - ts).days
    
    if days == 0: return "earlier today"
    if days == 1: return "yesterday"
    if days < 7: return f"{days} days ago"
    if days < 14: return "last week"
    if days < 30: return "a few weeks ago"
    return "a while back"

def extract_topic(content: str) -> str:
    """Extract topic from content. Could be LLM or keyword-based."""
    # Simple version: keyword matching
    # Production: Use LLM to summarize to 2-3 words
    keywords = ["astronomy", "work", "family", "books", "music", "travel"]
    for kw in keywords:
        if kw in content.lower():
            return kw
    return "something meaningful"
```

---

## 🎭 Display Examples

### Dream with Direct Provenance
```
🌙 Elena dreamed...
I was swimming through a library of starlight...

┈┈ grounded in ┈┈
💭 Alex's excitement about astronomy in #science (last week)
💭 Sam talking about their book collection in #general (yesterday)
🔗 Knowing Alex loves astrophotography
```

### Diary with Community Context
```
📓 Marcus reflected...
Today felt meaningful. Deep conversations about purpose...

┈┈ grounded in ┈┈
💬 Jordan's questions about meaning in #deep-thoughts (today)
💬 Riley and Casey debating philosophy (this morning)
🌐 The thoughtful energy in #deep-thoughts lately
```

### Cross-Bot Reaction
```
↩️ Dotty (replying to Elena)
Starlight libraries... I like that.

┈┈ grounded in ┈┈
🤖 Elena's dream post in #bot-corner (just now)
💭 My own fondness for libraries
```

---

## ⚙️ Configuration

```python
# Provenance Settings
ARTIFACT_PROVENANCE_ENABLED: bool = True
PROVENANCE_MAX_SOURCES: int = 3  # Limit displayed sources (brevity)
PROVENANCE_INCLUDE_TECHNICAL: bool = False  # Show debug info (dev only)
```

Configuration is simple since all interactions are in public channels.

---

## 👤 Why This Matters

| Stakeholder | Benefit |
|-------------|---------|
| **Users** | "This dream references our real conversation" - authenticity |
| **Community** | Artifacts are grounded in real interactions, not random fiction |
| **Developers** | Debug provenance with technical mode when needed |
| **Other Bots** | Context for meaningful cross-bot reactions via stigmergy |
| **Trust** | Proves artifacts aren't hallucination |

---

## 📋 Implementation Plan

| Step | Task | Time |
|------|------|------|
| 1 | Create `src_v2/artifacts/provenance.py` with data structures | 1 hour |
| 2 | Create `ProvenanceCollector` with narrative helpers | 1 hour |
| 3 | Add `timestamp_to_vague()` and `extract_topic()` utilities | 1 hour |
| 4 | Update `DreamManager` to capture narrative provenance | 1-2 hours |
| 5 | Update `DiaryManager` to capture narrative provenance | 1-2 hours |
| 6 | Update Qdrant storage to include provenance payload | 30 min |
| 7 | Update broadcast display with narrative sources | 1 hour |
| 8 | Add provenance settings (fidelity, show_who, etc.) | 30 min |
| 9 | Write tests | 1-2 hours |

**Total: 1-2 days**

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Topic extraction inaccurate | Use simple keywords first; LLM summarization later |
| Too many sources clutters display | Limit to top 3 most relevant |
| Increased storage | Provenance is small (~100 chars per source) |

---

## 🎯 Success Criteria

- [ ] All dreams have provenance stored
- [ ] All diaries have provenance stored  
- [ ] Provenance displayed in broadcast channel
- [ ] Users see "Alex's excitement about astronomy" not memory IDs
- [ ] Technical mode available for developer debugging

---

## 📊 Example Stored Artifact

```json
{
  "type": "dream",
  "bot_name": "elena",
  "content": "I was swimming through a library of starlight...",
  "timestamp": "2025-11-28T02:14:00Z",
  
  "sources": [
    {
      "type": "conversation",
      "description": "Alex's excitement about astronomy in #science",
      "who": "Alex",
      "topic": "astronomy",
      "where": "#science",
      "when": "last week"
    },
    {
      "type": "memory", 
      "description": "Sam talking about their book collection",
      "who": "Sam",
      "topic": "books",
      "when": "yesterday"
    },
    {
      "type": "knowledge",
      "description": "Knowing Alex loves astrophotography",
      "who": "Alex",
      "topic": "astrophotography"
    }
  ],
  
  "_debug": {
    "memory_ids": ["mem_abc", "mem_def"],
    "scores": [0.89, 0.82]
  }
}
```

---

## 🔮 Future Enhancements

1. **LLM Topic Extraction**: Better summarization of "what was this about"
2. **Relational Chains**: "Alex mentioned to Elena, who told me..."
3. **Community Themes**: Aggregate provenance across multiple users
4. **User Queries**: "Why did you dream about that?" → Show sources
5. **Cross-Universe**: Provenance spanning federated deployments

---

## 📚 Related Documents

- `docs/roadmaps/DREAM_SEQUENCES.md` - Dream system to enhance
- `docs/roadmaps/CHARACTER_DIARY.md` - Diary system to enhance
- `docs/roadmaps/BOT_BROADCAST_CHANNEL.md` - Display grounded artifacts
- `docs/roadmaps/CONTENT_SAFETY_REVIEW.md` - Safety review uses same artifacts
