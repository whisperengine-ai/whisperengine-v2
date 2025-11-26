# Phase A8: Image Generation Enhancements

**Priority:** High | **Time:** 3-4 days | **Complexity:** Low-Medium  
**Status:** 📋 Ready for Implementation  
**Depends On:** Phase B3 (Image Generation) ✅ Complete

---

## Executive Summary

Based on production observation of 1.5+ hour iterative image generation sessions (Nov 26, 2025), we've identified key improvements to enhance the user experience. Users treat image generation as **collaborative art direction**, iterating 10-15+ times on portraits to achieve desired likeness.

**Key Pain Points Identified:**
1. Character self-injection biases user portraits (gender, features)
2. No iteration memory ("keep X, change Y" is hard)
3. Negative associations emerge (e.g., "cult leader vibes")
4. Reference photo interpretation is ambiguous

**Production Evidence:** See [IMAGE_GENERATION_WORKFLOW.md](../features/IMAGE_GENERATION_WORKFLOW.md)

---

## Problem Statement

### Current State

The image generation system (Flux Pro 1.1) is functional and drives high engagement. However, production usage reveals friction points that cause 10-15 iteration cycles before user satisfaction:

| Issue | Frequency | User Impact |
|-------|-----------|-------------|
| Gender/presentation mismatch | ~40% of portrait sessions | 3-5 extra iterations |
| Likeness accuracy | ~90% of portrait sessions | 5-10 extra iterations |
| Unwanted style elements | ~30% of sessions | 2-3 extra iterations |
| Negative associations | ~10% of sessions | 2-3 extra iterations |

### Root Causes

1. **Character Self-Injection**
   - Character describes themselves in prompts ("as I imagine myself")
   - Female character traits bleed into user portrait requests
   - No separation between "character's vision" and "user's portrait"

2. **Stateless Generation**
   - Each image is generated independently
   - User says "keep everything but change the glasses" → entire new generation
   - No memory of previous prompt or user refinements

3. **No Negative Prompting**
   - Certain aesthetic combinations produce unwanted associations
   - "Spiritual + robes + cosmic" → "cult leader" archetype
   - No guardrails against common failure modes

4. **Ambiguous Reference Photos**
   - User provides photo → unclear intent
   - "This is me" vs "Use this style" vs "Combine with concept"
   - Bot guesses incorrectly, wastes iterations

---

## Proposed Solution

### Enhancement 1: Portrait Mode Detection

**Goal:** Automatically detect user portrait requests and avoid character self-injection.

**Trigger Phrases:**
```python
PORTRAIT_TRIGGERS = [
    "portrait of me",
    "picture of me",
    "photo of me",
    "selfie of me",
    "draw me",
    "make me",
    "what do I look like",
    "how do I look",
    "image of me",
]
```

**Implementation:**
```python
# In image_tools.py

def is_portrait_request(user_message: str) -> bool:
    """Detect if user is requesting their own portrait."""
    message_lower = user_message.lower()
    return any(trigger in message_lower for trigger in PORTRAIT_TRIGGERS)

async def construct_prompt(
    user_request: str,
    character_context: dict,
    user_context: dict,
    attached_image_description: Optional[str] = None
) -> str:
    if is_portrait_request(user_request):
        # PORTRAIT MODE: Don't inject character self-description
        return construct_portrait_prompt(
            user_request=user_request,
            user_facts=user_context.get("appearance_facts", []),
            reference_description=attached_image_description,
        )
    else:
        # CHARACTER MODE: Include character aesthetic
        return construct_character_blended_prompt(
            user_request=user_request,
            character_visual=character_context.get("visual_description"),
            character_aesthetic=character_context.get("art_style"),
        )
```

**Portrait Prompt Template:**
```python
PORTRAIT_TEMPLATE = """
{gender} person, {age_description}
{facial_features}
{clothing_style}
{accessories}
{background_setting}
{quality_modifiers}
"""
```

**Files Changed:**
- `src_v2/tools/image_tools.py` - Add detection logic, separate prompt paths

---

### Enhancement 2: Iteration Memory (Session Context)

**Goal:** Remember previous generation context for refinement requests.

**Session Model:**
```python
@dataclass
class ImageGenerationSession:
    user_id: str
    channel_id: str
    created_at: datetime
    
    # Previous generation context
    previous_prompt: str
    previous_image_url: str
    previous_refinements: List[str]
    
    # Accumulated user preferences
    confirmed_elements: List[str]  # "keep the glasses"
    rejected_elements: List[str]   # "no gloves"
    
    def is_active(self) -> bool:
        """Session expires after 30 minutes of inactivity."""
        return (datetime.utcnow() - self.created_at).seconds < 1800
```

**Refinement Detection:**
```python
REFINEMENT_TRIGGERS = [
    "keep everything",
    "same but",
    "change the",
    "remove the",
    "add the",
    "try again",
    "one more time",
    "same style",
    "like before",
]

def is_refinement_request(user_message: str) -> bool:
    message_lower = user_message.lower()
    return any(trigger in message_lower for trigger in REFINEMENT_TRIGGERS)
```

**Prompt Construction with Memory:**
```python
async def construct_refinement_prompt(
    session: ImageGenerationSession,
    new_feedback: str
) -> str:
    # Start with previous successful prompt
    base_prompt = session.previous_prompt
    
    # Apply accumulated preferences
    for element in session.rejected_elements:
        base_prompt = base_prompt.replace(element, "")
    
    # Add new refinement
    refinement_clause = f"\n\nREFINEMENT: {new_feedback}"
    
    # Add confirmed elements as emphasis
    if session.confirmed_elements:
        emphasis = ", ".join(session.confirmed_elements)
        refinement_clause += f"\n\nKEEP EXACTLY: {emphasis}"
    
    return base_prompt + refinement_clause
```

**Storage:** Redis with 30-minute TTL (session-based, not persistent)

**Files Changed:**
- New: `src_v2/image_gen/session.py` - Session management
- `src_v2/tools/image_tools.py` - Session-aware prompt construction
- `src_v2/core/cache.py` - Redis session storage

---

### Enhancement 3: Negative Prompt Library

**Goal:** Prevent common unwanted associations.

**Library Structure:**
```python
NEGATIVE_PROMPTS = {
    # Base negatives for all generations
    "base": [
        "low quality", "blurry", "distorted", "deformed",
        "bad anatomy", "extra limbs", "mutation",
    ],
    
    # Context-specific negatives
    "portrait": [
        "cult leader", "sinister", "evil", "creepy", "scary",
        "horror", "zombie", "demonic",
    ],
    
    "spiritual": [
        "cult", "religious extremism", "fanaticism", "sacrifice",
        "dark ritual", "occult horror",
    ],
    
    "cosmic": [
        "alien abduction", "horror", "dystopian", "apocalyptic",
        "lovecraftian", "eldritch horror",
    ],
    
    "fantasy": [
        "gore", "violence", "blood", "dark fantasy horror",
    ],
}

def get_negative_prompt(categories: List[str]) -> str:
    """Build negative prompt from relevant categories."""
    negatives = set(NEGATIVE_PROMPTS["base"])
    for category in categories:
        if category in NEGATIVE_PROMPTS:
            negatives.update(NEGATIVE_PROMPTS[category])
    return ", ".join(negatives)
```

**Category Detection:**
```python
def detect_prompt_categories(prompt: str) -> List[str]:
    categories = []
    prompt_lower = prompt.lower()
    
    if any(w in prompt_lower for w in ["portrait", "selfie", "photo of"]):
        categories.append("portrait")
    if any(w in prompt_lower for w in ["spiritual", "chakra", "meditation", "mystical"]):
        categories.append("spiritual")
    if any(w in prompt_lower for w in ["cosmic", "universe", "galaxy", "stars"]):
        categories.append("cosmic")
    if any(w in prompt_lower for w in ["fantasy", "magic", "wizard", "warrior"]):
        categories.append("fantasy")
    
    return categories
```

**Files Changed:**
- `src_v2/image_gen/prompts.py` - New file for prompt engineering
- `src_v2/tools/image_tools.py` - Use negative prompts in generation

---

### Enhancement 4: Reference Photo Intent Detection

**Goal:** Clarify how user wants reference photo used.

**Intent Categories:**
```python
class ReferenceIntent(Enum):
    PORTRAIT_LIKENESS = "portrait"      # "This is me"
    STYLE_REFERENCE = "style"           # "Use this style"
    CONCEPT_BLEND = "blend"             # "Combine with this concept"
    UNKNOWN = "unknown"                 # Need clarification
```

**Detection Logic:**
```python
PORTRAIT_INTENT_PHRASES = [
    "this is me", "that's me", "here's me", "picture of me",
    "here I am", "me irl", "selfie", "my photo",
]

STYLE_INTENT_PHRASES = [
    "like this", "this style", "similar to", "inspired by",
    "in this style", "aesthetic like",
]

BLEND_INTENT_PHRASES = [
    "combine with", "merge with", "blend with", "mix with",
    "add this to", "incorporate",
]

def detect_reference_intent(user_message: str) -> ReferenceIntent:
    message_lower = user_message.lower()
    
    if any(p in message_lower for p in PORTRAIT_INTENT_PHRASES):
        return ReferenceIntent.PORTRAIT_LIKENESS
    if any(p in message_lower for p in STYLE_INTENT_PHRASES):
        return ReferenceIntent.STYLE_REFERENCE
    if any(p in message_lower for p in BLEND_INTENT_PHRASES):
        return ReferenceIntent.CONCEPT_BLEND
    
    return ReferenceIntent.UNKNOWN
```

**Clarification Response (when UNKNOWN):**
```python
CLARIFICATION_PROMPT = """
I see you shared an image! To create the best result, help me understand:

1️⃣ **"This is me"** - I'll create a portrait that looks like you
2️⃣ **"Use this style"** - I'll use this as artistic inspiration  
3️⃣ **"Combine with [concept]"** - I'll blend this with something else

Which would you like?
"""
```

**Files Changed:**
- `src_v2/tools/image_tools.py` - Intent detection
- `src_v2/agents/reflective.py` - Clarification flow when needed

---

## Implementation Plan

### Day 1: Portrait Mode Detection
- [ ] Add `is_portrait_request()` detection function
- [ ] Create separate prompt construction paths
- [ ] Test with portrait vs. character-blend scenarios
- [ ] Update tool description for LLM

### Day 2: Negative Prompt Library
- [ ] Create `src_v2/image_gen/prompts.py`
- [ ] Build category-based negative prompt library
- [ ] Add category detection logic
- [ ] Integrate into generation pipeline
- [ ] Test with "cult leader" scenario

### Day 3: Iteration Memory
- [ ] Create `ImageGenerationSession` dataclass
- [ ] Add Redis session storage with TTL
- [ ] Implement refinement detection
- [ ] Build delta-based prompt construction
- [ ] Test "keep X, change Y" scenarios

### Day 4: Reference Intent & Polish
- [ ] Add reference intent detection
- [ ] Implement clarification flow
- [ ] End-to-end testing
- [ ] Documentation update

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Iterations to satisfaction (portrait) | 10-15 | 5-7 |
| Gender mismatch rate | ~40% | <10% |
| "Cult leader" incidents | ~10% | <2% |
| User complaints about iteration | Frequent | Rare |

---

## Cost Impact

| Change | Cost Impact |
|--------|-------------|
| Portrait mode detection | None (logic only) |
| Negative prompts | None (prompt modification) |
| Iteration memory | Minimal (Redis ops) |
| Reference clarification | +1 LLM call when needed (~$0.001) |

**Net Impact:** Neutral to slightly positive (fewer iterations = fewer generations needed)

---

## Files Changed

| File | Change Type | LOC Estimate |
|------|-------------|--------------|
| `src_v2/tools/image_tools.py` | Modify | +150 |
| `src_v2/image_gen/prompts.py` | New | +100 |
| `src_v2/image_gen/session.py` | New | +80 |
| `src_v2/core/cache.py` | Modify | +30 |
| `src_v2/agents/reflective.py` | Modify | +20 |
| **Total** | | **~380** |

---

## Feature Flags

```python
# settings.py

# Enable portrait mode detection (separate from character context)
ENABLE_PORTRAIT_MODE: bool = True

# Enable iteration memory for refinement requests
ENABLE_IMAGE_SESSION_MEMORY: bool = True

# Enable negative prompt injection
ENABLE_NEGATIVE_PROMPTS: bool = True

# Enable reference intent clarification
ENABLE_REFERENCE_CLARIFICATION: bool = True
```

---

## Testing Plan

### Unit Tests
- `test_is_portrait_request()` - Detection accuracy
- `test_construct_portrait_prompt()` - No character injection
- `test_refinement_detection()` - Delta identification
- `test_negative_prompt_categories()` - Category mapping

### Integration Tests
- Portrait flow end-to-end
- Refinement session continuity
- Clarification flow completion

### Production Validation
- A/B test: With/without enhancements
- Track iterations-to-satisfaction metric
- Monitor user feedback in community

---

## Related Documents

- [IMAGE_GENERATION_WORKFLOW.md](../features/IMAGE_GENERATION_WORKFLOW.md) - Production session analysis
- [IMAGE_GENERATION.md](./IMAGE_GENERATION.md) - Original implementation spec
- [CHARACTER_AS_AGENT.md](../architecture/CHARACTER_AS_AGENT.md) - Latency tolerance evidence

---

## Version History

- v1.0 (Nov 26, 2025) - Initial spec based on production observation. Identified 4 key enhancements from 1.5-hour iterative portrait session analysis.
