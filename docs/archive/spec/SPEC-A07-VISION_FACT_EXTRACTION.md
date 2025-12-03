# Vision-to-Knowledge Fact Extraction

**Status:** Planned  
**Priority:** Medium  
**Complexity:** Medium  
**Estimated Cost Impact:** +$0.002-0.005 per image

## Problem Statement

Currently, when users upload images:
1. Vision LLM analyzes and describes the image ✅
2. Description is stored in vector memory (searchable) ✅
3. **No structured facts are extracted to the knowledge graph** ❌

This means if a user uploads a selfie showing "brown hair, blue eyes, beard", the bot:
- CAN recall "you sent me a picture once" via semantic search
- CANNOT reliably recall "you have brown hair" as a structured fact

The bot may hallucinate that it "saved these details" when it didn't actually extract them to the knowledge graph.

## Design Challenges

### 1. Subject Identification Problem
**Who is in the image?**

| Image Type | Subject | Should Extract Facts? |
|------------|---------|----------------------|
| Selfie | User themselves | ✅ Yes - user's appearance |
| Photo of friend | Someone else | ❌ No - would incorrectly attribute to user |
| Photo of celebrity | Public figure | ❌ No - not about user |
| Photo with user + others | User + others | ⚠️ Partial - need to identify which person is user |
| Pet photo | User's pet | ✅ Yes - user's pet details |
| Photo of user's car | User's belonging | ✅ Yes - user owns this |
| Meme | Random person/thing | ❌ No - not about user |
| Screenshot | UI/text | ❌ No - nothing to extract |
| Artwork | Art/illustration | ❌ No - nothing personal |

### 2. Classification Accuracy
An LLM classifier could categorize images, but:
- **False positives:** Photo of user's friend → incorrectly extract as user's appearance
- **False negatives:** Actual selfie → miss extraction opportunity
- **Cost:** Extra LLM call per image (~$0.001)
- **Latency:** Adds 1-2s to image processing

### 3. User Confirmation vs Automatic
| Approach | Pros | Cons |
|----------|------|------|
| **Automatic** | Seamless UX | False positives pollute knowledge graph |
| **Ask user** | Accurate | Interrupts flow, annoying |
| **Confidence threshold** | Balance | Still has edge cases |

## Proposed Solutions

### Option A: User-Triggered Extraction (Recommended)
User explicitly says "this is me" or "this is my cat Luna":

```
// Pseudocode
on_image_with_context(image, user_message):
  description = analyze_image(image)
  
  if user_indicates_self(user_message):
    // "this is me", "here's a pic of myself", "that's me on the left"
    extract_facts(description, subject="user")
  
  elif user_indicates_possession(user_message):
    // "this is my cat", "here's my new car", "my apartment"
    extract_facts(description, subject="user's belonging")
  
  else:
    // Just store description in memory, no fact extraction
    store_memory(description)
```

**Trigger phrases for self:**
- "this is me"
- "here's a pic of myself"
- "that's me"
- "selfie"
- "how do I look"

**Trigger phrases for possessions:**
- "this is my [pet/car/house/etc]"
- "here's my new..."
- "meet my [pet name]"

### Option B: Classification + Confidence Threshold
```
// Pseudocode
on_image(image):
  category, confidence = classify_image(image)
  
  if category == "selfie" and confidence > 0.9:
    extract_facts(description, subject="user")
  elif category == "personal" and confidence > 0.85:
    extract_facts(description, subject="user's belonging")
  else:
    store_memory_only(description)
```

**Downsides:**
- Extra LLM call per image
- Still can't distinguish "photo of me" vs "photo of my friend"
- Confidence calibration is tricky

### Option C: Retrospective Extraction (Advanced)
Don't extract facts immediately. When user later asks "what do I look like?":

```
// Pseudocode
on_appearance_question(user_id):
  visual_memories = search_memories(user_id, "selfie OR portrait OR appearance")
  
  for memory in visual_memories:
    if not memory.facts_extracted:
      facts = extract_facts_from_description(memory.description)
      // Ask user: "I found this description from a photo you sent. Is this you?"
      if user_confirms:
        store_facts(facts)
```

**Pros:** Zero false positives (user confirms)
**Cons:** Delayed knowledge, requires user interaction

## Implementation Plan (Option A)

### Phase 1: Context-Aware Extraction
1. Detect trigger phrases in user message accompanying image
2. If trigger detected, extract facts from visual description
3. Frame fact extraction appropriately based on subject type

### Phase 2: Metadata Tagging
1. Add `subject_type` to image memory metadata
2. Values: `unknown`, `user_self`, `user_possession`, `other_person`, `generic`
3. Enable filtering in future queries

### Phase 3: Correction Mechanism
1. User can say "that wasn't me" to remove incorrect facts
2. Track fact provenance (source: image analysis)
3. Enable bulk correction if needed

## Files to Modify

```
src_v2/vision/manager.py
  - Add subject detection from user message context
  - Conditional fact extraction based on subject type

src_v2/discord/bot.py  
  - Pass user message context to vision manager
  - Handle correction commands ("that wasn't me")

src_v2/knowledge/extractor.py
  - Add visual-specific extraction prompts
  - Handle subject framing (user vs user's pet, etc.)
```

## Cost Analysis

| Scenario | Current | With Option A |
|----------|---------|---------------|
| User sends meme | $0.003 (vision) | $0.003 (no change) |
| User sends selfie, no context | $0.003 | $0.003 (no extraction) |
| User sends selfie + "this is me" | $0.003 | $0.008 (vision + fact extraction) |

Option A only adds cost when user explicitly provides context, avoiding waste on non-personal images.

## Open Questions

1. **Should we ask for confirmation?** 
   - "I see you have brown hair and blue eyes. Want me to remember that?"
   - Adds friction but ensures accuracy

2. **How to handle group photos?**
   - User says "that's me on the left" - how to extract only their description?
   - May need more sophisticated prompting

3. **Should visual facts expire?**
   - Appearance changes over time
   - Maybe tag with timestamp and weight older facts lower?

4. **Privacy considerations?**
   - Storing detailed physical descriptions
   - Should require explicit opt-in?

## References

- `src_v2/vision/manager.py` - Current vision analysis implementation
- `src_v2/knowledge/extractor.py` - Fact extraction logic
- `src_v2/workers/worker.py` - Background knowledge extraction worker
