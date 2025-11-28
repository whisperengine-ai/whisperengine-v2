# Phase B3: Image Generation (Visual Imagination)

**Priority:** High | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete (v2.0 - Nov 28, 2025)

## 🎯 Objective
Give characters the ability to "imagine" and share images based on the conversation context. This adds a visual modality to their expression, allowing them to send "selfies", drawings, or visual representations of their thoughts.

## 🧠 The Concept
Characters should not just be text generators. They should have a "mind's eye". When a user asks "what do you look like right now?" or "draw me a sheep", the character should be able to generate an image that matches their persona, current emotional state, and the conversation context.

## 🛠️ Technical Implementation

### 1. Provider: Flux (via BFL API)
We use the **Flux Pro 1.1** model for high-quality image generation.
- **Model:** `flux-pro-1.1` (Best quality)
- **Integration:** HTTP API call to BFL (Black Forest Labs)

### 2. Intent Detection (v2.0)
Image generation is triggered via **LLM-based intent detection** in the `ComplexityClassifier`:

```python
# classifier.py returns structured output
{
    "complexity": "COMPLEX_MID",
    "intents": ["image"]  # detected by LLM semantic analysis
}
```

This replaces the old approach of relying on the Reflective Agent to detect image requests during tool selection. Now, intent is detected upfront and complexity is promoted to ensure tool access.

**Key Change:** If "image" intent is detected but complexity was classified as "SIMPLE", the bot automatically promotes it to "COMPLEX_MID" to enable Reflective Mode (which has access to the `generate_image` tool).

### 3. Tool: `generate_image`
A tool available to the `ReflectiveAgent`.

**Tool Definition:**
```python
class GenerateImageTool(BaseTool):
    name = "generate_image"
    description = "Generates an image based on a prompt. Use this when the user asks to see something, or when you want to show a visual representation of your thoughts."
    
    async def _run(self, prompt: str, style: str = "photorealistic"):
        # ... implementation ...
```

### 4. Prompt Engineering (The "Mind's Eye")
The raw prompt from the user ("draw a sheep") is insufficient. We inject the character's **visual persona**.

**Prompt Construction:**
```
{character_visual_description} + {current_scene_context} + {user_prompt} + {style_modifiers}
```

### 5. Discord Integration
- The tool returns an image URL.
- Images are cached in Redis with user_id as key
- Bot extracts pending images and attaches them to Discord response

## 📋 Implementation (v2.0)

**Intent Detection Flow:**
```
Message → ComplexityClassifier (LLM) → detected_intents["image"] → Promote to COMPLEX_MID → ReflectiveAgent → generate_image tool → Flux API → Discord
```

**Feature Flag Gating:**
- `ENABLE_IMAGE_GENERATION` (default: true) - controls whether intent detection includes "image"
- If disabled, the classifier prompt doesn't ask for image intents

**Daily Quota:**
- `DAILY_IMAGE_QUOTA` (default: 5 per user per day)
- Managed by `src_v2/core/quota.py`

## 💰 Cost Management
- Flux generation costs ~$0.04 per image
- **Daily Quota:** Max images per user per day (`DAILY_IMAGE_QUOTA`)
- **Trust Gating:** Only users with Trust Score > threshold can request images (`IMAGE_GEN_MIN_TRUST`)

## 📁 Related Files
- `src_v2/agents/classifier.py` - Intent detection (v2.0)
- `src_v2/tools/image_tools.py` - `GenerateImageTool`
- `src_v2/image_gen/service.py` - Flux API integration
- `src_v2/core/quota.py` - Daily quota management
- `src_v2/discord/bot.py` - Intent handling and complexity promotion
- `docs/features/IMAGE_GENERATION_WORKFLOW.md` - Production learnings
