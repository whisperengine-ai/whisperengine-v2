# PRD-004: Multi-Modal Perception (Vision, Voice, Image Generation)

**Status:** ✅ Implemented (P0/P1 Complete, P2 Deferred)  
**Owner:** Mark Castillo  
**Created:** November 2025  
**Updated:** December 2025

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Multi-modal experience vision |
| **Proposed by** | Mark (product expansion) |
| **Catalyst** | Text-only interactions missed rich context from images and voice |

---

## Problem Statement

Text-only AI characters miss significant context from images, voice, and other media that users share. They also can't express themselves through creative visual output. This limits the richness of interaction and makes the character feel less capable than modern AI should be.

**User pain points:**
- "I shared an image but the bot can't see it"
- "I want the bot to draw what we're talking about"
- "Text responses feel flat sometimes—I want to hear the character"
- "The character should understand what I'm showing, not just what I'm saying"

---

## User Stories

- **As a user sharing images**, I want the character to understand and respond to what I share, so my visual communication is recognized.

- **As a creative user**, I want to ask the character to generate images, so we can visualize ideas together.

- **As an immersed user**, I want to hear the character's voice, so the experience feels more personal.

- **As a storytelling user**, I want the character to generate art for our stories, so our narratives come to life visually.

---

## Requirements

### Must Have (P0)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Image Understanding** | Process user-uploaded images | ✅ |
| **Image Description** | Extract and respond to image content | ✅ |
| **Image Generation** | Generate images on user request | ✅ |
| **Character Self-Portraits** | Character can generate images of themselves | ✅ |

### Should Have (P1)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Voice Responses** | TTS audio responses on request | ✅ |
| **Per-Character Voices** | Each character has unique voice | ✅ |
| **Intent Detection** | Automatically detect when user wants voice/image | ✅ |
| **Quotas** | Daily limits per user for expensive operations | ✅ |

### Nice to Have (P2)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Image-to-Facts** | Extract knowledge from images into graph | 📋 Deferred |
| **Voice Input** | Process user voice messages | 📋 |
| **Video Understanding** | Process short video clips | 📋 |
| **Live Voice Channels** | Real-time TTS in voice channels | 📋 |

---

## User Experience

### Image Understanding

```
User: [Uploads photo of sunset over ocean]
Elena: Oh, that's beautiful! 🌅 The way the light hits the water 
       reminds me of bioluminescence patterns I studied. Where was 
       this taken? The color gradation in that sky is remarkable.
```

### Image Generation

```
User: Can you draw yourself reading by a window?
Elena: *imagines the scene* 

[Generates image via Flux Pro 1.1]
[Posts image to channel]

Elena: Here I am, lost in a book about marine conservation. 
       The afternoon light is my favorite for reading. 📚
```

### Voice Responses

```
User: Say that in your voice!
Elena: [Generates TTS via ElevenLabs]
       [Uploads audio file]
       
       *the audio plays with Elena's warm, slightly accented voice*
```

### Intent Detection

```
User: I want to hear what you sound like
       [Classifier detects: intent=voice]
       [Routes to voice response pipeline]

User: Show me what you'd look like as a mermaid
       [Classifier detects: intent=image_self]
       [Routes to image generation with character self-reference]
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Image Generation Usage** | 30% of active users request at least one image | Feature usage logs |
| **Voice Adoption** | 20% of users try voice at least once | Feature usage logs |
| **Image Quality Rating** | >4/5 average user rating | Reaction analysis |
| **Intent Detection Accuracy** | >90% correct classification | Manual sampling |
| **Quota Satisfaction** | <10% users hit daily quota | Quota hit tracking |

---

## Privacy & Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| **Inappropriate Image Requests** | Content safety prompt filtering | ✅ |
| **Image-Based Harassment** | Generated images reviewed for safety | ✅ |
| **Voice Cloning Concerns** | Only use approved TTS voices | ✅ |
| **Resource Abuse** | Daily quotas per user | ✅ |
| **NSFW Image Uploads** | Not currently filtered | ⚠️ Risk |

---

## Cost Structure

| Modality | Provider | Cost per Unit | Daily Quota |
|----------|----------|---------------|-------------|
| **Image Generation** | BFL (Flux Pro 1.1) | ~$0.04-0.10 | 5 images |
| **Voice Synthesis** | ElevenLabs | ~$0.01-0.05 | 10 clips |
| **Image Understanding** | OpenAI GPT-4o | ~$0.01-0.03 | Unlimited |

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| OpenAI Vision API | ✅ | Image understanding |
| BFL / Replicate / Fal | ✅ | Image generation |
| ElevenLabs | ✅ | Text-to-speech |
| Complexity Classifier | ✅ | Intent detection |
| Quota Manager | ✅ | Per-user limits |

---

## Technical Reference

- Vision pipeline: [`docs/architecture/VISION_PIPELINE.md`](../architecture/VISION_PIPELINE.md)
- Multi-modal perception: [`docs/architecture/MULTI_MODAL_PERCEPTION.md`](../architecture/MULTI_MODAL_PERCEPTION.md)
- Image generation: [`src_v2/image_gen/service.py`](../../src_v2/image_gen/service.py)
- Voice responses: [`src_v2/voice/response.py`](../../src_v2/voice/response.py)
- TTS manager: [`src_v2/voice/tts.py`](../../src_v2/voice/tts.py)
- Quota manager: [`src_v2/core/quota.py`](../../src_v2/core/quota.py)
