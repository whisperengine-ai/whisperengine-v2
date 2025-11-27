# Phase B3: Image Generation (Visual Imagination)

**Priority:** High | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete

## 🎯 Objective
Give characters the ability to "imagine" and share images based on the conversation context. This adds a visual modality to their expression, allowing them to send "selfies", drawings, or visual representations of their thoughts.

## 🧠 The Concept
Characters should not just be text generators. They should have a "mind's eye". When a user asks "what do you look like right now?" or "draw me a sheep", the character should be able to generate an image that matches their persona, current emotional state, and the conversation context.

## 🛠️ Technical Implementation

### 1. Provider: Flux (via Replicate/Fal.ai/BFL)
We will use the **Flux.1** model (Schnell or Pro) for high-quality image generation.
- **Model:** `black-forest-labs/flux-1-schnell` (Fast, good quality) or `flux-1-pro` (Best quality)
- **Integration:** HTTP API call to provider (Replicate, Fal.ai, or direct BFL API)

### 2. New Tool: `generate_image`
A new tool available to the `AgentEngine` (specifically the Router or Reflective agent).

**Tool Definition:**
```python
class GenerateImageTool(BaseTool):
    name = "generate_image"
    description = "Generates an image based on a prompt. Use this when the user asks to see something, or when you want to show a visual representation of your thoughts. The prompt should be descriptive."
    
    async def _run(self, prompt: str, style: str = "photorealistic"):
        # ... implementation ...
```

### 3. Prompt Engineering (The "Mind's Eye")
The raw prompt from the user ("draw a sheep") is insufficient. We need to inject the character's **visual persona**.

**Prompt Construction:**
```
{character_visual_description} + {current_scene_context} + {user_prompt} + {style_modifiers}
```

*Example:*
User: "Send me a selfie"
Constructed Prompt: "A photorealistic selfie of Elena, a 24-year-old woman with silver hair and cybernetic eyes, smiling softly in a dimly lit server room with neon blue accents. High quality, 8k, cinematic lighting."

### 4. Discord Integration
- The tool returns an image URL.
- The bot downloads the image (or passes the URL if Discord supports it directly, but downloading + re-uploading is safer for persistence).
- Sends as an attachment.

## 📋 Implementation Steps

1.  **Settings & Config:**
    - Add `FLUX_API_KEY` to `.env`
    - Add `IMAGE_GEN_PROVIDER` (default: `replicate` or `fal`)
    - Add `IMAGE_GEN_MODEL` (default: `flux-schnell`)

2.  **Image Service (`src_v2/image_gen/service.py`):**
    - `ImageGenerator` class
    - `generate(prompt: str) -> str` (returns URL)
    - Error handling & retries

3.  **Tool Creation (`src_v2/tools/image_tools.py`):**
    - `GenerateImageTool`
    - Integration with `AgentEngine`

4.  **Character Config Update:**
    - Add `visual_description` field to `character.md` or `character.yaml`.
    - This is CRITICAL for consistent character appearance.

5.  **Discord Output:**
    - Handle image URLs in the response handler.

## 💰 Cost Management
- Flux generation costs money per image.
- **Rate Limiting:** Max X images per user per day.
- **Trust Gating:** Only users with Trust Score > 10 can request images (prevents abuse).

## 📝 Notes
- "Flux account" likely refers to an API key for a service hosting Flux. We need to confirm which one (Replicate, Fal, etc.).
- We should support "style" presets (selfie, oil painting, sketch, cyberpunk).
