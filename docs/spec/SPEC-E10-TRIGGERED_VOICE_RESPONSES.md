# Triggered Voice Responses - TTS Audio Attachments

**Document Version:** 2.0  
**Created:** November 27, 2025  
**Updated:** November 28, 2025  
**Status:** ✅ Implemented  
**Priority:** Medium  
**Complexity:** 🟢 Low  
**Estimated Time:** 2-3 days

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Multi-modal experience vision |
| **Proposed by** | Mark (product vision) |
| **Catalyst** | Text-only responses felt limited |
| **Key insight** | Voice adds emotional depth to character interactions |

---

## Executive Summary

Enable characters to respond with both **text AND an attached TTS audio file** when triggered. This creates a richer, more immersive experience where users can read the response AND hear the character's voice—similar to voice messages but as a downloadable/playable MP3 attachment.

**Implementation Status:** Voice responses are now fully implemented with LLM-based intent detection (as of v2.0).

---

## 👤 User Experience

### What Users Will See

```
User: @Elena tell me about how you felt when you first saw a whale shark

Elena: 🔊 *Elena takes a breath... her voice carries across the waves...*

🐋✨ Elena speaks...

The first time I saw a whale shark, my heart stopped for a moment,
A gentle giant gliding through the blue, silent and immense.
I felt so small, so wonderfully insignificant,
Just another creature sharing this vast ocean home...

📎 elena_voice.mp3 (276 KB)
▶️ 0:00 / 0:18
```

### Trigger Methods

Voice responses are now triggered via **LLM-based intent detection** (not keyword matching).

| Trigger | Example | Notes |
|---------|---------|-------|
| **Semantic intent** | "tell me how you feel as an audio file" | LLM detects voice intent |
| **Natural language** | "speak to me about your dreams" | LLM understands "speak" semantically |
| **Audio request** | "send me a voice message" | LLM detects voice intent |
| **Any phrasing** | "can you say that out loud?" | LLM handles varied phrasing |

The old regex/keyword-based trigger system (`VoiceTriggerDetector`) has been **deprecated** in favor of the LLM classifier.

---

## 🔧 Technical Design

### Architecture Overview (v2.0)

```
Message Received
      │
      ▼
┌─────────────────────────────┐
│ ComplexityClassifier (LLM)  │  ← Classifies complexity + detects intents
│  - Returns: complexity      │     (voice, image, search)
│  - Returns: intents[]       │
└─────────────────────────────┘
      │
      ▼ (if "voice" in intents AND ENABLE_VOICE_RESPONSES=true)
┌─────────────────────────────┐
│ Generate Response           │  ← Normal LLM response
└─────────────────────────────┘
      │
      ▼
┌─────────────────────────────┐
│ VoiceResponseManager        │  ← Generate TTS via ElevenLabs
│  - Check quota              │
│  - Generate audio           │
└─────────────────────────────┘
      │
      ▼
┌─────────────────────────────┐
│ Discord Send                │  ← Text + discord.File attachment
└─────────────────────────────┘
```

### Key Components

#### 1. ComplexityClassifier (Intent Detection)

**Location:** `src_v2/agents/classifier.py`

The classifier uses LangChain structured output to detect intents:

```python
class ClassificationOutput(BaseModel):
    complexity: ClassificationResult  # SIMPLE, COMPLEX_LOW, etc.
    intents: List[str]  # ["voice", "image", "search"]
```

The LLM prompt includes intent detection instructions that are **conditionally added** based on feature flags:

- `"voice"` intent: Only included if `ENABLE_VOICE_RESPONSES=true`
- `"image"` intent: Only included if `ENABLE_IMAGE_GENERATION=true`

This keeps the prompt clean and avoids false positives when features are disabled.

#### 2. VoiceResponseManager

**Location:** `src_v2/voice/response.py`

Handles TTS generation with quota management:

```python
async def generate_voice_response(self, text: str, character: Character, user_id: str) -> Optional[Tuple[str, str]]:
    # Check quota first
    if not await quota_manager.check_quota(user_id, 'audio'):
        raise QuotaExceededError('audio', limit, usage)
    
    # Generate TTS via ElevenLabs
    audio_bytes = await tts_manager.generate_speech(text, voice_id)
    
    # Increment quota on success
    await quota_manager.increment_usage(user_id, 'audio')
    
    return (file_path, filename)
```

#### 3. Bot Integration

**Location:** `src_v2/discord/bot.py`

```python
# After generating response
complexity, detected_intents = await engine.classify_complexity(...)

if settings.ENABLE_VOICE_RESPONSES and "voice" in detected_intents:
    should_trigger_voice = True
    logger.info(f"Voice intent detected for user {user_id}")
```

### Removed Components

The following are **deprecated** and no longer used:

- ~~`src_v2/voice/trigger.py`~~ (deleted)
- ~~`VoiceTriggerDetector` class~~ (removed)
- ~~`ux.yaml` `voice.trigger_keywords`~~ (removed from all characters)

---

## 📁 Configuration

### Character-Level Voice Config

In `characters/{name}/ux.yaml`:

```yaml
# Voice Response Configuration (v2.0)
voice:
  voice_id: "EXAVITQu4vr4xnSDxMaL"  # ElevenLabs voice ID (optional, falls back to env)
  intro_template: "🔊 *{name} speaks...*"  # Narrative intro before voice response
```

**Removed fields:**
- ~~`trigger_keywords`~~ - Now handled by LLM intent detection
- ~~`enabled`~~ - Controlled by global `ENABLE_VOICE_RESPONSES` flag
            return true
        
        // Check for explicit voice keywords
        message_lower = message.lower()
        for keyword in keywords:
            if keyword in message_lower:
                return true
        
        // Check for emotional/narrative prompts (optional)
        if character_config.voice_on_emotional_prompts:
            if contains_emotional_markers(message):
                return true
        
        return false
```

#### 2. Voice Response Generator

```
// Pseudocode - src_v2/voice/response.py

class VoiceResponseGenerator:
    function generate_voice_response(text, character_name, voice_id) -> VoiceResponse:
        // Strip markdown/emoji for cleaner TTS
        clean_text = strip_for_tts(text)
        
        // Generate audio bytes via existing TTSManager
        audio_bytes = await tts_manager.generate_speech(clean_text, voice_id)
        
        if audio_bytes is None:
            return VoiceResponse(success=false, error="TTS generation failed")
        
        // Create Discord file
        filename = f"{character_name}_voice.mp3"
        discord_file = discord.File(BytesIO(audio_bytes), filename=filename)
        
        return VoiceResponse(
            success=true,
            audio_file=discord_file,
            duration_estimate=len(clean_text) / 15  // ~15 chars/sec spoken
        )
    
    function strip_for_tts(text) -> str:
        // Remove emoji, markdown formatting, URLs
        text = remove_emoji(text)
        text = remove_markdown(text)
        text = remove_urls(text)
        // Keep punctuation for natural pauses
        return text.strip()
```

#### 3. Integration with Bot Response Pipeline

```
// Pseudocode - modification to src_v2/discord/bot.py

async function send_response(message, response_text, character):
    files = []
    
    // Check for pending images (existing)
    response_text, image_files = await extract_pending_images(response_text, user_id)
    files.extend(image_files)
    
    // NEW: Check for voice response
    if voice_trigger_detector.should_include_voice(original_message, character.voice_config):
        voice_response = await voice_generator.generate_voice_response(
            text=response_text,
            character_name=character.name,
            voice_id=character.voice_id or settings.ELEVENLABS_VOICE_ID
        )
        if voice_response.success:
            files.append(voice_response.audio_file)
            // Add narrative intro
            intro = character.voice_config.voice_intro or f"🔊 *{character.name}'s voice emerges...*"
            response_text = f"{intro}\n\n{response_text}"
    
    // Send with attachments
    await message.channel.send(content=response_text, files=files)
```

---

## 📁 Configuration

### Character-Level Voice Config

Add to `characters/{name}/ux.yaml`:

```yaml
# Voice Response Configuration
voice:
  enabled: true                    # Can this character use voice responses?
  voice_id: "EXAVITQu4vr4xnSDxMaL" # ElevenLabs voice ID (overrides env default)
  always_include: false            # Always attach voice? (expensive!)
  
  # Trigger keywords (in addition to global defaults)
  trigger_keywords:
    - "speak to me"
    - "your voice"
    - "say it aloud"
    - "tell me how you felt"
  
  # Voice intro text (shown before response)
  intro_template: "🔊 *{name} gathers breath... her voice forms...*\n\n🌊✨ *{name} speaks...*"
  
  # What to strip from TTS (cleaner audio)
  strip_patterns:
    - emoji
    - markdown
    - urls
    - parentheticals  # Remove (like this) from speech
```

### Global Settings

In `src_v2/config/settings.py`:

```python
# --- Voice Response ---
ENABLE_VOICE_RESPONSES: bool = False  # Feature flag (must be true for voice intent detection)
VOICE_RESPONSE_MAX_LENGTH: int = 1000  # Max chars to convert to TTS (cost control)
VOICE_RESPONSE_MIN_TRUST: int = 0  # Trust level required (0 = anyone)

# --- Quotas ---
DAILY_AUDIO_QUOTA: int = 10  # Max audio clips a user can generate per day
```

### Environment Variables

```bash
# .env.{character}
ELEVENLABS_API_KEY=your-api-key
ELEVENLABS_VOICE_ID=default-voice-id  # Fallback if not in ux.yaml
ELEVENLABS_MODEL_ID=eleven_multilingual_v2  # Better for non-English
ENABLE_VOICE_RESPONSES=true
```

---

## 💰 Cost Considerations

### ElevenLabs Pricing (as of Nov 2025)

| Plan | Characters/Month | Cost | Per 1K Chars |
|------|------------------|------|--------------|
| Free | 10,000 | $0 | N/A |
| Starter | 30,000 | $5 | ~$0.17 |
| Creator | 100,000 | $22 | ~$0.22 |
| Pro | 500,000 | $99 | ~$0.20 |

### Cost Control Strategies

1. **Feature flag per character** - Only enable for premium/specific characters
2. **Trust gating** - Require minimum trust level (e.g., 20 = Acquaintance)
3. **Max length cap** - Truncate long responses before TTS (1000 chars default)
4. **Cooldown per user** - Limit voice responses per user per hour
5. **Trigger-only mode** - Only generate voice when explicitly requested
6. **Caching** - Cache common responses (e.g., greetings) - low priority

### Estimated Usage

| Scenario | Responses/Day | Avg Chars | Monthly Chars | Monthly Cost |
|----------|---------------|-----------|---------------|--------------|
| Low (trigger-only) | 10 | 300 | 90,000 | ~$20 |
| Medium (emotional prompts) | 50 | 400 | 600,000 | ~$120 |
| High (always-on) | 200 | 500 | 3,000,000 | ~$600 |

**Recommendation:** Start with trigger-only mode (`always_include: false`).

---

## 🚀 Implementation Status

### ✅ Completed (v2.0 - November 28, 2025)

- [x] LLM-based intent detection in `ComplexityClassifier`
- [x] `VoiceResponseManager` with quota checking
- [x] Bot integration with `detected_intents` handling
- [x] Daily quota per user (`DAILY_AUDIO_QUOTA`)
- [x] Feature flag gating (`ENABLE_VOICE_RESPONSES`)
- [x] Dynamic intent prompts (only ask for voice intent if feature enabled)
- [x] Removed deprecated `VoiceTriggerDetector` and `trigger_keywords`
- [x] ElevenLabs TTS integration via `TTSManager`

### 🔮 Future Enhancements

- [ ] Slash command `/voice <prompt>` - Explicit voice request
- [ ] Voice reactions - React with 🔊 to get voice version of any message
- [ ] Voice cloning - Custom character voices (ElevenLabs Voice Lab)
- [ ] Streaming playback - Play in voice channel instead of file attachment

---

## 📊 Metrics & Monitoring

Track in InfluxDB:

```python
# Voice response metrics
Point("voice_response")
    .tag("character", character_name)
    .tag("trigger_type", "keyword|explicit|emotional")
    .field("text_length", len(text))
    .field("audio_bytes", len(audio_bytes))
    .field("generation_time_ms", duration)
    .field("success", 1 or 0)
```

Dashboard queries:
- Voice responses per day per character
- Average audio generation time
- Total characters sent to ElevenLabs (for billing)
- Error rate

---

## 🔮 Future Enhancements

- **Slash command** `/voice <prompt>` - Explicit voice request
- **Voice reactions** - React with 🔊 to get voice version of any message
- **Voice cloning** - Custom character voices (ElevenLabs Voice Lab)
- **Streaming playback** - Play in voice channel instead of file attachment
- **Multi-voice** - Different voices for different moods/contexts

---

## 📋 Checklist for New Characters

When adding voice to a new character:

1. [x] Set `ENABLE_VOICE_RESPONSES=true` in `.env.{character}`
2. [x] Add `ELEVENLABS_VOICE_ID` or set in `ux.yaml`
3. [x] (Optional) Customize `intro_template` in `ux.yaml`
4. [x] Test with natural language prompts ("send me a voice message", "say that out loud")

**Note:** No `trigger_keywords` needed - the LLM handles intent detection automatically.

---

## Appendix: Sample ux.yaml Voice Configs

### Elena (Marine Biologist)

```yaml
voice:
  voice_id: "EXAVITQu4vr4xnSDxMaL"  # Soft, warm female voice
  intro_template: "🔊 *Elena takes a breath... her voice carries across the waves...*\n\n🌊✨ *Elena speaks...*"
```

### Marcus (Musician)

```yaml
voice:
  voice_id: "pNInz6obpgDQGcFmaJgB"  # Warm male voice
  intro_template: "🎵 *Marcus clears his throat... the melody begins...*\n\n🎸✨ *Marcus sings...*"
```

### NotTaylor (Parody)

```yaml
voice:
  intro_template: "🔊 *NotTaylor speaks...*"
  # Uses ELEVENLABS_VOICE_ID from .env.nottaylor
```

---

**Document maintained by:** WhisperEngine Team  
**Last updated:** November 28, 2025
