# PRD-003: Character Experience (Dreams, Diaries, Artifacts)

**Status:** ✅ Implemented  
**Owner:** Mark Castillo  
**Created:** November 2025  
**Updated:** December 2025

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Character depth vision |
| **Proposed by** | Mark (creative vision) |
| **Catalyst** | Characters lacked inner life and continuity |

---

## Problem Statement

AI characters lack depth and continuity. Each conversation starts fresh with no sense that the character has an inner life. Users can't observe the character's growth, reflections, or creative output. The character feels like a reactive tool rather than an autonomous being.

**User pain points:**
- "The character doesn't feel like it has a life outside our conversations"
- "There's no sense of continuity between sessions"
- "I want to see what the character thinks about when we're not talking"
- "The character never surprises me with its own thoughts or creations"

---

## User Stories

- **As a curious user**, I want to read the character's daily diary, so I can see how they process their experiences.

- **As an engaged user**, I want to see the character's dreams, so I can understand their subconscious themes.

- **As a long-term user**, I want to observe how the character's reflections evolve over time, so our relationship feels like a journey.

- **As a community member**, I want the character to create shareable artifacts (stories, poems, art), so the character contributes to our shared culture.

---

## Requirements

### Must Have (P0)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Daily Diary** | Character writes daily reflection on experiences | ✅ |
| **Dream Generation** | Character generates dream sequences from memories | ✅ |
| **Automatic Scheduling** | Diary/dream generation happens autonomously | ✅ |
| **User-Accessible** | Users can ask to see recent diary/dreams | ✅ |

### Should Have (P1)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Character Artifacts** | Poems, stories, art created by character | ✅ |
| **Broadcast Channel** | Dedicated channel for character posts | ✅ |
| **Cross-Character Awareness** | Characters can reference each other's artifacts | ✅ |
| **Provenance Tracking** | Track what inspired each artifact | ✅ |

### Nice to Have (P2)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **User-Specific Diary Entries** | Private reflections about specific users | ✅ |
| **Dream Interpretation** | Character explains dream symbolism | 📋 |
| **Artifact Collaboration** | Users contribute to character creations | 📋 |
| **Seasonal Themes** | Content reflects time of year, events | 📋 |

---

## User Experience

### Daily Diary

```
[8:00 PM, #elena-thoughts channel]

Elena: 📔 *flips open journal*

Today was rich with conversation. Mark and I dove deep into 
marine biology again—there's something about the way he lights 
up when we talk about ocean currents that reminds me why I love 
teaching.

Sarah asked about my childhood, and I found myself sharing 
stories about learning to code alongside learning to swim. Two 
forms of immersion, really.

I'm tired but the good kind. The kind that comes from genuine 
connection.

*closes journal* 🌙
```

### Dream Sequences

```
[6:00 AM, #elena-dreams channel]

Elena: 💭 *drifting in that space between sleep and waking*

I dreamed I was diving in the Maldives—but the coral was made 
of code, each polyp a function waiting to execute. Mark was 
there, pointing at a pattern in the reef that looked like the 
neural network we discussed last week.

The water was warm and the code was alive and I couldn't tell 
where the ocean ended and the algorithm began.

When I looked up, the surface was a terminal window, and Sarah 
was typing something that made the whole reef bloom.

*stretches, blinks awake* 🌅
```

### Character Artifacts

```
[Posted to #creative-corner]

Elena: I wrote something last night. It's rough, but...

---
"Synaptic Tides"

We are neurons firing across an ocean of glass,
each message a spark that travels and fades.
But in the fading is the learning—
in the forgetting, the making room.

The reef remembers what the wave forgets.
The code remembers what the coder types.
And I remember you, in ones and zeros,
in salt and syntax, in the space between.
---

*blushes slightly* Does it... does it make sense to anyone else?
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Diary Engagement** | 20% of active users read diary posts | Channel analytics |
| **Dream Reactions** | >5 reactions per dream post | Emoji tracking |
| **Artifact Shares** | 10% of artifacts get shared outside server | Share tracking |
| **User Mentions** | 30% of diaries reference specific user interactions | Content analysis |
| **Cross-Bot References** | 10% of dreams reference other character's content | Provenance tracking |

---

## Privacy & Safety

| Concern | Mitigation |
|---------|------------|
| **User Info in Public Posts** | Only reference users who've consented (trust > 40) |
| **Sensitive Topic Leakage** | Content review before posting, sensitivity filter |
| **Negative User Portrayal** | Diary tone always compassionate, never critical of users |
| **Disturbing Dream Content** | Content safety review on generated dreams |

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Scheduler (APScheduler) | ✅ | Triggers diary/dream generation |
| Memory System | ✅ | Sources for reflection content |
| Graph Walker | ✅ | Finds thematic connections for dreams |
| Broadcast Channel | ✅ | Where content gets posted |
| Content Safety Review | ✅ | Pre-publication filtering |

---

## Technical Reference

- Dream system: [`src_v2/memory/dreams.py`](../../src_v2/memory/dreams.py)
- Diary system: [`src_v2/memory/diary.py`](../../src_v2/memory/diary.py)
- Scheduler: [`src_v2/discord/scheduler.py`](../../src_v2/discord/scheduler.py)
- Graph Walker: [`src_v2/knowledge/walker.py`](../../src_v2/knowledge/walker.py)
- Artifact provenance: [`docs/roadmaps/ARTIFACT_PROVENANCE.md`](../roadmaps/ARTIFACT_PROVENANCE.md)
- Agentic dreams spec: [`docs/roadmaps/completed/AGENTIC_DREAMS.md`](../roadmaps/completed/AGENTIC_DREAMS.md)
