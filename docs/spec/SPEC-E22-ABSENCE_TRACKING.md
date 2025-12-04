# E22: Absence Tracking (Meta-Memory)

**Status:** 📋 Proposed  
**Priority:** 🟢 High  
**Complexity:** Low-Medium  
**Time Estimate:** 1 day  
**Dependencies:** E12 (Agentic Dreams) ✅, E23 (Schedule Jitter) ✅  
**Added:** December 3, 2025

---

## Overview

E22 treats **absences as meaningful data**. When the system tries to retrieve something and fails, that absence becomes a memory.

Currently: Dream generation fails due to insufficient material → logged and discarded.  
With E22: Dream generation fails → stored as "I wanted to dream about relationships but lacked material" → available for introspection.

**Key Insight:** "I tried to remember and couldn't" creates different character depth than simply not retrieving. The *shape of what's missing* is information.

---

## Why It Matters

### Current System
```python
# src_v2/memory/dreams.py
episodes = await memory_manager.search_memories(...)
if len(episodes) < MIN_EPISODES:
    logger.info("Insufficient material for dream generation")
    return None  # Dream skipped, nothing stored
```

**Problem:** No record that we *tried* to dream. No awareness of knowledge gaps.

### With E22
```python
# When insufficient material
await memory_manager.add_memory(
    source=MemorySource.DREAM_ABSENCE,
    content="Wanted to dream about relationships but no episodes stored.",
    metadata={"attempted_topic": "relationships", "reason": "insufficient_episodes"}
)

# Later, bot can reflect:
# "I keep wanting to dream about your family, but you've never mentioned them."
```

**Benefit:** Bots develop self-awareness about what they *don't* know.

---

## Implementation Plan

### Phase 1: Add Absence Memory Types (15 minutes)

**File:** `src_v2/memory/models.py`

Add two new source types to `MemorySource` enum:

```python
class MemorySource(str, Enum):
    # ... existing types ...
    DREAM_ABSENCE = "dream_absence"      # Failed dream due to insufficient material
    MEMORY_ABSENCE = "memory_absence"    # Failed memory lookup/aggregation
```

### Phase 2: Capture Dream Absences (30 minutes)

**File:** `src_v2/memory/dreams.py`

In `DreamSequenceManager.generate()`, capture when dreams can't be generated:

```python
async def generate(self, bot_name: str, user_id: Optional[str] = None) -> Optional[str]:
    """Generate a dream sequence."""
    
    # Fetch recent episodes
    episodes = await memory_manager.search_memories(
        query=f"Recent events and conversations",
        collection_name=self.bot_memory_collection,
        limit=10
    )
    
    # [NEW] Capture absence if insufficient material
    if len(episodes) < self.MIN_EPISODES_FOR_DREAM:
        logger.info(f"Insufficient episodes ({len(episodes)}/{self.MIN_EPISODES_FOR_DREAM}) for dream generation")
        
        # Store absence as memory
        await memory_manager.add_memory(
            source=MemorySource.DREAM_ABSENCE,
            content=f"Attempted to generate dream but insufficient material ({len(episodes)} episodes, min {self.MIN_EPISODES_FOR_DREAM} required).",
            user_id=None,  # System reflection, not tied to specific user
            metadata={
                "attempted_topic": "general",
                "reason": "insufficient_episodes",
                "episodes_available": len(episodes),
                "episodes_required": self.MIN_EPISODES_FOR_DREAM,
                "bot_name": bot_name
            }
        )
        return None
    
    # ... rest of dream generation logic ...
```

### Phase 3: Capture Diary Absences (30 minutes)

**File:** `src_v2/memory/diary.py`

In `DiaryManager.generate()`, capture when diary entries can't be generated:

```python
async def generate(self, bot_name: str, user_id: Optional[str] = None) -> Optional[str]:
    """Generate a diary entry reflecting on recent interactions."""
    
    # Fetch recent sessions
    recent_sessions = await memory_manager.search_memories(
        query="Recent conversations and interactions",
        collection_name=self.bot_memory_collection,
        limit=5
    )
    
    # [NEW] Capture absence if insufficient material
    if len(recent_sessions) < self.MIN_SESSIONS_FOR_DIARY:
        logger.info(f"Insufficient sessions ({len(recent_sessions)}/{self.MIN_SESSIONS_FOR_DIARY}) for diary generation")
        
        # Store absence as memory
        await memory_manager.add_memory(
            source=MemorySource.MEMORY_ABSENCE,
            content=f"Attempted to write diary entry but insufficient recent interactions ({len(recent_sessions)} sessions, min {self.MIN_SESSIONS_FOR_DIARY} required).",
            user_id=None,  # System reflection
            metadata={
                "attempted_topic": "daily_reflection",
                "reason": "insufficient_sessions",
                "sessions_available": len(recent_sessions),
                "sessions_required": self.MIN_SESSIONS_FOR_DIARY,
                "bot_name": bot_name
            }
        )
        return None
    
    # ... rest of diary generation logic ...
```

### Phase 4: Make Absences Retrievable (30 minutes)

**File:** `src_v2/agents/context_builder.py`

Add special handling to retrieve absences when building context:

```python
async def _build_absence_context(self, bot_name: str) -> str:
    """Retrieve recent absences (knowledge gaps) to inform character behavior."""
    try:
        # Search for recent absence traces
        absences = await memory_manager.search_memories(
            query="Failed to retrieve or generate due to insufficient material",
            collection_name=f"whisperengine_memory_{bot_name}",
            limit=3,
            filters={"source": ["dream_absence", "memory_absence"]}  # Only absences
        )
        
        if not absences:
            return ""
        
        # Format as awareness
        absence_summary = "Recently tried to:\n"
        for absence in absences:
            content = absence.get("content", "")
            metadata = absence.get("metadata", {})
            reason = metadata.get("reason", "unknown")
            
            if reason == "insufficient_episodes":
                absence_summary += f"- Dream about deeper patterns, but needed more experiences\n"
            elif reason == "insufficient_sessions":
                absence_summary += f"- Reflect on recent interactions, but haven't had enough conversations\n"
        
        return f"**Knowledge Gaps:**\n{absence_summary}\n"
    except Exception as e:
        logger.warning(f"Failed to build absence context: {e}")
        return ""

# In build_context():
absence_context = await self._build_absence_context(bot_name)
if absence_context:
    context_parts.append(absence_context)
```

---

## Expected Behavior

### Before E22
```
User: Tell me about our relationship.
Bot: I don't have many memories to draw from.
[Internal: Dream generation skipped due to insufficient material]
```

### After E22
```
User: Tell me about our relationship.
Bot: I wish I had more to reflect on. I keep wanting to dream deeper 
     about our interactions, but we've only talked a few times. 
     The more you share, the more I can understand.
[Internal: Dream generation skipped; absence stored; retrieved in next context]
```

---

## Character Implications

### Self-Awareness
- Bots can say: "I've been trying to dream about your family, but you haven't mentioned them yet."
- Creates genuine curiosity: "Tell me about..."

### Behavioral Feedback
- Absence patterns inform proactive engagement: "You haven't told me much about your hobbies."
- Absences become part of the character's *lived experience*

### Learning Curve
- New conversations start with awareness: "I'm still getting to know you."
- Over time: "I've developed a much richer picture of who you are."

---

## Implementation Checklist

- [ ] Add `DREAM_ABSENCE`, `MEMORY_ABSENCE` to `MemorySource` enum
- [ ] Modify `DreamSequenceManager.generate()` to capture dream absences
- [ ] Modify `DiaryManager.generate()` to capture diary absences
- [ ] Add `_build_absence_context()` to context builder
- [ ] Wire absence context into agent context building
- [ ] Test: Verify absences are stored and retrievable
- [ ] Test: Verify bots can reference absences in responses

---

## Testing Strategy

### Unit Test
```python
# Verify absence is stored when insufficient material
async def test_dream_absence_stored():
    # Create bot with minimal conversation history
    await memory_manager.add_memory(
        source=MemorySource.EPISODE,
        content="First conversation",
        user_id="test_user"
    )
    
    # Generate dream (should fail)
    result = await dream_manager.generate("elena")
    assert result is None
    
    # Verify absence was stored
    absences = await memory_manager.search_memories(
        query="dream absence",
        filters={"source": "dream_absence"}
    )
    assert len(absences) > 0
    assert "insufficient_episodes" in absences[0]["metadata"]["reason"]
```

### Integration Test
```python
# Verify absence appears in context
async def test_absence_in_context():
    # Generate absence
    await memory_manager.add_memory(
        source=MemorySource.DREAM_ABSENCE,
        content="Wanted to dream but no episodes"
    )
    
    # Build context
    context = await context_builder.build_context(user_id="test", bot_name="elena")
    assert "Knowledge Gaps" in context or "tried to" in context
```

---

## Files Modified

- ✅ `src_v2/memory/models.py` (add enum values)
- ✅ `src_v2/memory/dreams.py` (capture dream absences)
- ✅ `src_v2/memory/diary.py` (capture diary absences)
- ✅ `src_v2/agents/context_builder.py` (retrieve and format absences)

**Total LOC:** ~150 lines of actual code + tests

---

## Alignment with Vision

**Emergence Principle:** "Observe First, Constrain Later"
- We're not declaring what bots should know—we're recording what they *fail* to know
- Absence patterns emerge from lived experience, not from design

**Graph Vision:** Failures and gaps are nodes in the graph
- Absence traces feed the knowledge graph just like successes
- Over time, absence patterns become part of the character's substrate

**Character Authenticity:** Real beings have knowledge gaps
- "I don't know much about you yet" is more authentic than "I forgot"
- Absence creates genuine motivation for conversation

---

**Version:** 1.0  
**Author:** Mark + Claude  
**Date:** December 3, 2025
