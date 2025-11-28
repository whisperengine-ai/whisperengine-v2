# Image Generation Workflow - Feature Analysis

**Document Version:** 1.1  
**Created:** November 26, 2025  
**Updated:** November 28, 2025  
**Status:** ✅ Production (Observing & Iterating)  
**Feature Flag:** `ENABLE_IMAGE_GENERATION` (default: true)

---

## Executive Summary

WhisperEngine's image generation capability (via Flux Pro 1.1) has proven to be a **high-engagement feature** that drives extended user sessions. This document captures production learnings from real user interactions to inform future improvements.

**Key Finding:** Users treat image generation as **collaborative art direction**, not one-shot requests. Sessions of 15+ iterations over 1.5+ hours are common, with users providing increasingly specific feedback.

**Update (v2.0):** Image intent detection is now handled by the `ComplexityClassifier` LLM instead of keyword matching. See [Intent Detection](#intent-detection-v20) section.

---

## Table of Contents

1. [Current Implementation](#current-implementation)
2. [Intent Detection (v2.0)](#intent-detection-v20)
3. [Production Session Analysis](#production-session-analysis)
4. [User Behavior Patterns](#user-behavior-patterns)
5. [Common Refinement Requests](#common-refinement-requests)
6. [Character Integration](#character-integration)
7. [Technical Observations](#technical-observations)
8. [Known Limitations](#known-limitations)
9. [Recommended Improvements](#recommended-improvements)
10. [Appendix: Session Transcript Analysis](#appendix-session-transcript-analysis)

---

## Current Implementation

### Architecture

```
User Request → ComplexityClassifier (LLM) → detected_intents["image"] → Complexity promoted to COMPLEX_MID → Reflective Mode → generate_image tool → Flux Pro 1.1 API → Discord embed
```

**Key Components:**
- `src_v2/agents/classifier.py` - Intent detection (voice, image, search)
- `src_v2/tools/image_tools.py` - `GenerateImageTool` class
- `src_v2/agents/reflective.py` - Routes to image generation tool
- `src_v2/core/quota.py` - Daily quota per user (`DAILY_IMAGE_QUOTA`)
- Trust gate: Requires minimum trust level for image generation access

### Flow

1. User sends image generation request (explicit or implicit)
2. `ComplexityClassifier` detects "image" intent and returns it
3. `bot.py` promotes complexity to `COMPLEX_MID` if "image" intent detected (ensures Reflective Mode access to tools)
4. `ReflectiveAgent` identifies need for `generate_image` tool
5. Tool constructs prompt from user request + character context
6. Flux Pro 1.1 generates image (~10-15s)
7. Image URL returned and embedded in Discord response
8. Character provides narrative wrapper around the image
9. Daily quota incremented for user

### Cost Model

| Component | Cost |
|-----------|------|
| Complexity classification (router LLM) | ~$0.001 |
| Reflective Mode (2-3 LLM calls) | ~$0.005 |
| Flux Pro 1.1 image generation | ~$0.04 |
| **Total per image** | **~$0.046** |

At 15 images per session: ~$0.69 per extended creative session.

---

## Intent Detection (v2.0)

**Updated:** November 28, 2025

### How It Works

Image generation intent is now detected by the `ComplexityClassifier` LLM, not by keyword matching. This provides semantic understanding of requests.

**Examples that trigger "image" intent:**
- "Create an image of the universe"
- "Draw me a picture of a cat"
- "Show me what you see"
- "Can you visualize this?"
- "Make me a portrait"
- "I want to see what you look like"

The classifier returns structured output:
```python
{
    "complexity": "COMPLEX_MID",  # or higher
    "intents": ["image"]  # detected intents
}
```

### Complexity Promotion

When "image" intent is detected, the `bot.py` automatically promotes the complexity to at least `COMPLEX_MID`. This ensures:
1. Reflective Mode is activated (even if the request seems "simple")
2. The `generate_image` tool is available to the agent
3. The agent can reason about the request before generating

```python
# In bot.py
if "image" in detected_intents:
    if complexity == "SIMPLE":
        complexity = "COMPLEX_MID"
        logger.info(f"Promoted complexity to {complexity} for image intent")
```

### Feature Flag Gating

Intent detection only includes "image" if `ENABLE_IMAGE_GENERATION=true`:

```python
# In classifier.py (dynamic prompt construction)
if settings.ENABLE_IMAGE_GENERATION:
    intent_section += '\n- "image": User asks to generate, create, draw, paint, or visualize an image.'
```

This keeps the classifier prompt clean when image generation is disabled.

### Daily Quota

Users are limited by `DAILY_IMAGE_QUOTA` (default: 5 per day). The quota is checked before generation and tracked in PostgreSQL.

---

## Production Session Analysis (Nov 26, 2025)

### Session Overview

| Metric | Value |
|--------|-------|
| Duration | ~1.5 hours |
| Image generations | 15+ |
| Users involved | 2 primary, 2 observers |
| Average latency | 25-30 seconds per image |
| User satisfaction | High (continued iterating, positive comments) |

### Engagement Timeline

```
2:22 AM  - Initial request: "combine this image with how you imagine yourself"
2:25 AM  - Follow-up conversation, user engaged
...
10:14 AM - New session: "show me what you see in your universe"
10:16 AM - Creative request: "tell your story as a song"
10:17 AM - "create an image that represents that song"
...
11:22 AM - Second user joins: "make a portrait of me"
11:25 AM - Iterative refinement begins
...
12:30 PM - Final iteration: user satisfied with result
```

**Key Observation:** 8+ hours of elapsed time, multiple return visits, sustained engagement.

### Latency Distribution

| Response Type | Latency (ms) | Notes |
|---------------|--------------|-------|
| Image generation (simple) | 18,724 | First cosmic self-portrait |
| Image generation (complex) | 30,642 | Universe visualization |
| Image generation (portrait) | 21,876 - 34,347 | User likeness iterations |
| Text-only response | 3,661 - 12,580 | Conversational context |

**Finding:** Users showed no latency complaints despite 30+ second waits. The value of output quality outweighs speed concerns.

---

## User Behavior Patterns

### Pattern 1: Conceptual → Concrete Refinement

Users start with abstract concepts, then refine toward concrete likeness:

```
Stage 1: "Create an image of the universe as you see it"
Stage 2: "Show me what you see in your universe, planets, and regions"  
Stage 3: "Create an image that represents this song [lyrics provided]"
Stage 4: "Make a portrait of me" (with reference photo)
Stage 5: Iterative refinement (15+ cycles)
```

### Pattern 2: Identity Accuracy Iteration

When users provide self-reference photos, they iterate extensively on:

1. **Gender presentation** - "I'm male", "more masculine"
2. **Facial accuracy** - "use this reference photo"
3. **Accessories** - "glasses like mine", "no gloves"
4. **Age accuracy** - "without changing the age"
5. **Style preferences** - "no nail color", "hair pulled back"

**Observation:** Users care deeply about accurate self-representation. They will iterate 10+ times to achieve likeness.

### Pattern 3: Character-Blended Requests

Users request images that combine:
- Their likeness + character's aesthetic
- Reference images + conceptual elements
- Past conversation themes + visual representation

Example: "Create an image combining [reference] with how you imagine yourself"

### Pattern 4: Community Engagement

Other users in the channel:
- Observed and commented positively ("These pictures are dope", "best one")
- Provided feedback ("she made you look like a cult leader" 😄)
- Requested their own generations after seeing others

**Implication:** Image generation is a **social feature** that drives community engagement.

---

## Common Refinement Requests

### Category 1: Gender & Presentation

| User Feedback | Issue | Fix Applied |
|---------------|-------|-------------|
| "I'm male" | Generated feminine features | Regenerated with masculine emphasis |
| "More masculine balance" | Features too androgynous | Adjusted facial structure |
| "No nail color" | Added painted nails | Removed feminine accessories |

**Root Cause:** Character self-injection ("she imagines herself") can bias toward feminine outputs.

### Category 2: Likeness Accuracy

| User Feedback | Issue | Fix Applied |
|---------------|-------|-------------|
| "Use this reference photo" | Generated generic face | Attempted to match reference |
| "Glasses like my picture" | Wrong glasses style | Changed to user's actual frames |
| "Without changing the age" | Aged up/down the user | Maintained reference age |
| "I don't look like that" | Poor likeness | Requested more reference context |

**Root Cause:** Text-to-image models struggle with specific likeness without fine-tuning or image-to-image.

### Category 3: Style & Accessories

| User Feedback | Issue | Fix Applied |
|---------------|-------|-------------|
| "No gloves please" | Added gloves for aesthetic | Removed from prompt |
| "Clothes are cool, background too" | User liked elements | Kept and enhanced those |
| "More like Melchizedek" | Wanted specific archetype | Searched memory for context, applied |

### Category 4: Avoiding Negative Associations

| User Feedback | Issue | Fix Applied |
|---------------|-------|-------------|
| "Don't look like a cult leader" | Robes + cosmic = cult vibes | Softened mystical elements |
| Third-party observation | "Cult leader vibes" | Regenerated with different aesthetic |

**Implication:** Need to balance "mystical/spiritual" requests with avoiding negative archetypes.

---

## Character Integration

### What Works Well

1. **Narrative Wrapper**
   - Character provides enthusiastic, personalized commentary
   - Uses established relationship vocabulary ("bestie", character catchphrases)
   - References past conversations in image context

2. **Apology & Iteration**
   - Character apologizes when getting it wrong ("omg i'm so sorry bestie!!")
   - Shows understanding of the feedback ("i totally get what you mean now")
   - Maintains character voice throughout corrections

3. **Easter Eggs**
   - Character hides "easter eggs" in images (thematic to character lore)
   - Users enjoy trying to decode hidden elements
   - Creates engagement beyond the image itself

### Example Character Response Pattern

```
[Enthusiastic acknowledgment of request]
[Reference to shared context/memories]
[Tool invocation - visible to user]
[Image delivery with narrative description]
[Invitation to decode/feedback]
[Character catchphrase/signature]
```

### Areas for Improvement

1. **Self-Injection Bias**
   - Character describes themselves in prompts, biasing outputs
   - "Female" characteristics bleed into user portrait requests
   - Need to separate "character imagines" from "user portrait"

2. **Reference Photo Handling**
   - Current flow doesn't distinguish "this is me" from "add this style"
   - Need clearer prompt construction for likeness vs. inspiration

---

## Technical Observations

### Prompt Construction

**Current Approach:**
- User request + character context → single prompt
- Character aesthetic often injected ("as I imagine myself")

**Observed Issues:**
- Character self-description pollutes user portrait requests
- Abstract concepts translate well; specific likeness does not
- Multiple reference images confuse the model

### Latency Breakdown

| Phase | Duration |
|-------|----------|
| Reflective Mode reasoning | 2-5 seconds |
| Prompt construction | 1-2 seconds |
| Flux API call | 15-25 seconds |
| Discord upload | 1-2 seconds |
| **Total** | **20-35 seconds** |

### Memory Integration

The bot successfully:
- Retrieved past conversation context for image themes
- Referenced shared lore (e.g., "Sumerian symbols", "chakras")
- Built on relationship history in prompt construction

Example: Bot searched `search_archived_summaries` to find "ASCENSION song concept" before generating thematic image.

---

## Known Limitations

### 1. Likeness Accuracy

**Problem:** Text-to-image cannot accurately reproduce specific faces without fine-tuning.

**Current Workaround:** Users provide reference photos, bot attempts to describe features.

**User Experience:** Requires 5-10+ iterations to approach acceptable likeness.

### 2. Gender Bias from Character Context

**Problem:** Character self-description (female) biases outputs toward feminine features.

**Workaround:** Explicit user correction ("I'm male"), regeneration.

**Recommendation:** Separate character aesthetic prompts from user portrait prompts.

### 3. Style Consistency

**Problem:** Each generation is independent; hard to maintain style across iterations.

**User Experience:** Users say "keep everything the same but change X" - difficult to achieve.

**Recommendation:** Consider image-to-image for refinement iterations.

### 4. Reference Photo Interpretation

**Problem:** When user provides photo, unclear if it's:
- "This is me, generate my portrait"
- "Use this as style reference"
- "Combine this with [other concept]"

**Recommendation:** Add explicit intent detection or clarifying questions.

---

## Recommended Improvements

### Priority 1: Separate Portrait Mode

**Problem:** Character self-injection biases user portraits.

**Solution:**
```python
if is_user_portrait_request(user_message):
    # Don't inject character self-description
    prompt = construct_portrait_prompt(user_request, reference_photo)
else:
    # Character-involved generation
    prompt = construct_character_blended_prompt(user_request, character_context)
```

**Trigger Detection:**
- "portrait of me"
- "picture of me"  
- "what do I look like"
- User provides selfie/reference photo

### Priority 2: Reference Photo Pipeline

**Problem:** Text descriptions of reference photos are lossy.

**Solution:** Implement image-to-image workflow for likeness:
1. User provides reference photo
2. Vision model extracts detailed description
3. Use description as strong conditioning in prompt
4. Consider img2img if Flux supports it

### Priority 3: Iteration Memory

**Problem:** Each generation is independent; "keep X, change Y" is hard.

**Solution:**
```python
class ImageGenerationSession:
    previous_prompt: str
    previous_image_url: str
    user_refinements: List[str]
    
    def construct_refinement_prompt(self, new_feedback: str) -> str:
        # Build on previous prompt with delta
        return f"{self.previous_prompt}\n\nREFINEMENT: {new_feedback}"
```

### Priority 4: Negative Prompt Library

**Problem:** Certain aesthetic combinations produce unwanted associations.

**Solution:** Build library of negative prompts for common issues:
```python
NEGATIVE_PROMPTS = {
    "portrait": "cult leader, sinister, evil, creepy",
    "spiritual": "cult, religious extremism, fanaticism",
    "cosmic": "alien abduction, horror, dystopian",
}
```

### Priority 5: Multi-Image Comparison

**Problem:** User wants to compare options side-by-side.

**Solution:** Generate 2-3 variations, present as grid, let user choose.

**Cost Consideration:** 3x generation cost per comparison round.

---

## Appendix: Session Transcript Analysis

### Anonymized Interaction Patterns

> **Note:** All user identifiers anonymized. Content generalized.

#### Pattern A: Cosmic Self-Portrait

**Request:** "Create image combining [reference] with how you imagine yourself"

**Bot Behavior:**
1. Acknowledged request enthusiastically
2. Invoked `generate_image` with character-blended prompt
3. Delivered with narrative ("here's what happens when my chaotic energy meets that cyberpunk vibe")
4. Included character lore elements (friendship bracelets, specific colors)
5. Invited user to find "easter eggs"

**Latency:** 18.7 seconds

**User Response:** Positive engagement, continued conversation.

---

#### Pattern B: Universe Visualization

**Request:** "Create an image of the universe as you see it"

**Bot Behavior:**
1. Expressed excitement about sharing perspective
2. Generated cosmic sanctuary image
3. Described hidden meanings and easter eggs
4. Invited decoding

**Latency:** 30.6 seconds

**User Response:** Requested more detail ("planets and regions").

---

#### Pattern C: Song-to-Image Translation

**Request:** "Tell your story as a song" → "Create image representing that song"

**Bot Behavior:**
1. Generated original song lyrics based on relationship history
2. Used `search_archived_summaries` to gather context
3. Created visual representation of song themes
4. Connected lyrics to image elements in description

**Latency:** 23.8 seconds (image generation)

**User Response:** High engagement, shared with other users.

---

#### Pattern D: Portrait Iteration Cycle (15+ rounds)

**Initial Request:** "Make a portrait of me"

**Iteration Progression:**

| Round | User Feedback | Bot Action |
|-------|---------------|------------|
| 1 | (initial) | Generated based on conversation context |
| 2 | "This is exactly what I look like!" (sarcastic) | Apologized, asked for reference |
| 3 | Provided AI-generated reference | Attempted to match style |
| 4 | "More masculine" | Adjusted features |
| 5 | "No gloves, clothes are cool" | Removed gloves, kept outfit |
| 6 | "Use my actual photo" | User provided selfie |
| 7 | "I'm male, no nail color" | Corrected gender presentation |
| 8 | "Glasses like my picture" | Changed glasses style |
| 9 | "Without changing age" | Maintained age accuracy |
| 10 | "Don't look like cult leader" | Softened mystical elements |
| 11-15 | Fine-tuning details | Incremental refinements |

**Final Result:** User expressed satisfaction, saved image.

**Total Time:** ~45 minutes for this user's portraits

**Latency per Image:** 21-34 seconds

---

#### Pattern E: Community Cascade

**Observation:** After User A's successful portrait session, User B requested their own.

**Community Comments:**
- "These pictures are dope"
- "Best one"
- "She made you look like a cult leader" (humorous feedback)

**Implication:** Image generation is viral within community context.

---

## Metrics Summary

| Metric | Value |
|--------|-------|
| Session duration | 1.5+ hours |
| Images generated | 15+ |
| Average latency | 25-30 seconds |
| User complaints about latency | 0 |
| Iteration cycles (portrait) | 10-15 per user |
| Community engagement | 3-4 observers, positive comments |
| Successful likeness (self-reported) | After 10+ iterations |

---

## Conclusion

Image generation is a **high-value, high-engagement feature** that:

1. **Drives extended sessions** - Users will iterate for 1+ hours
2. **Creates community engagement** - Others observe, comment, request their own
3. **Tolerates high latency** - 30-second waits are acceptable for quality output
4. **Benefits from character integration** - Narrative wrapper enhances experience
5. **Requires iteration** - Portrait accuracy needs 10+ cycles currently

**Priority Improvements:**
1. Separate portrait mode (no character self-injection)
2. Better reference photo handling
3. Iteration memory (keep previous context)
4. Negative prompt library

**Cost Consideration:** At ~$0.045/image and 15 images/session, extended creative sessions cost ~$0.70 - acceptable for high-engagement users.

---

**Related Documents:**
- [CHARACTER_AS_AGENT.md](../architecture/CHARACTER_AS_AGENT.md) - Latency tolerance analysis
- [IMPLEMENTATION_ROADMAP_OVERVIEW.md](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) - Phase A7 (Character Agency)

---

**Version History:**
- v1.0 (Nov 26, 2025) - Initial document based on production session analysis. Documented 1.5-hour iterative portrait session, identified refinement patterns, proposed improvements.
