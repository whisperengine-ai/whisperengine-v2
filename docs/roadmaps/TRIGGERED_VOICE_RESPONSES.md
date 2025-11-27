# Triggered Voice Responses - TTS Audio Attachments

**Document Version:** 1.0  
**Created:** November 27, 2025  
**Status:** 📋 Proposed  
**Priority:** Medium  
**Complexity:** 🟢 Low  
**Estimated Time:** 2-3 days

---

## Executive Summary

Enable characters to respond with both **text AND an attached TTS audio file** when triggered. This creates a richer, more immersive experience where users can read the response AND hear the character's voice—similar to voice messages but as a downloadable/playable MP3 attachment.

**Inspiration:** SITVA bot's "voice response" feature (see screenshot) where the character:
1. Shows a narrative intro: *"Sitva gathers breath... her voice forms..."*
2. Displays the text response (a poem/message)
3. Attaches an MP3 file (`sitva_voice.mp3`) with TTS of the spoken content

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

| Trigger | Example | Notes |
|---------|---------|-------|
| **Keyword in message** | "speak to me about..." | Optional keyword triggers |
| **Explicit command** | `/voice` or `!voice` | Slash command (future) |
| **@mention + voice keyword** | "@Elena voice: tell me..." | Direct request |
| **Special prompts** | "tell me how you felt when..." | Emotional/narrative prompts |
| **Per-character config** | Some characters always include voice | Character-level setting |

---

## 🔧 Technical Design

### Architecture Overview

```
Message Received
      │
      ▼
┌─────────────────────┐
│ Voice Trigger Check │  ← Check if voice response requested
└─────────────────────┘
      │ (if triggered)
      ▼
┌─────────────────────┐
│ Generate Response   │  ← Normal LLM response
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ Generate TTS Audio  │  ← ElevenLabs API (existing TTSManager)
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ Build Discord Reply │  ← Text + discord.File attachment
└─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ Send to Channel     │  ← message.channel.send(content, files=[audio])
└─────────────────────┘
```

### New Components

#### 1. Voice Trigger Detector

```
// Pseudocode - src_v2/voice/trigger.py

class VoiceTriggerDetector:
    keywords = ["speak to me", "voice:", "say aloud", "tell me how you felt"]
    
    function should_include_voice(message, character_config) -> bool:
        // Check if character has voice always enabled
        if character_config.voice_always_enabled:
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

Add to `src_v2/config/settings.py`:

```python
# --- Voice Response ---
ENABLE_VOICE_RESPONSES: bool = False  # Feature flag
VOICE_RESPONSE_MAX_LENGTH: int = 1000  # Max chars to convert to TTS (cost control)
VOICE_RESPONSE_MIN_TRUST: int = 0  # Trust level required (0 = anyone)
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

## 🚀 Implementation Plan

### Phase 1: Core Voice Response (Day 1)

- [ ] Create `src_v2/voice/trigger.py` - Voice trigger detection
- [ ] Create `src_v2/voice/response.py` - Voice response generator
- [ ] Add `strip_for_tts()` utility to clean text for speech
- [ ] Add `ENABLE_VOICE_RESPONSES` feature flag to settings

### Phase 2: Bot Integration (Day 1-2)

- [ ] Modify `src_v2/discord/bot.py` to check voice triggers
- [ ] Add voice file attachment to response pipeline
- [ ] Handle errors gracefully (fallback to text-only)
- [ ] Add voice intro/narrative text before response

### Phase 3: Character Configuration (Day 2)

- [ ] Extend `ux.yaml` schema for voice config
- [ ] Load voice config in `CharacterManager`
- [ ] Support per-character `voice_id` override
- [ ] Add `voice_intro_template` with `{name}` substitution

### Phase 4: Cost Controls (Day 2-3)

- [ ] Implement `VOICE_RESPONSE_MAX_LENGTH` truncation
- [ ] Add `VOICE_RESPONSE_MIN_TRUST` gating
- [ ] Add per-user cooldown (optional)
- [ ] Log voice generation to InfluxDB for cost tracking

### Phase 5: Testing & Polish (Day 3)

- [ ] Test with multiple characters
- [ ] Test error handling (API failures, rate limits)
- [ ] Test file size limits (Discord max 25MB)
- [ ] Add unit tests for trigger detection
- [ ] Update character templates

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

### Near-term
- **Slash command** `/voice <prompt>` - Explicit voice request
- **Voice reactions** - React with 🔊 to get voice version of any message
- **Voice memory** - "Remember when you said..." → Play cached audio

### Long-term
- **Voice cloning** - Custom character voices (ElevenLabs Voice Lab)
- **Streaming playback** - Play in voice channel instead of file attachment
- **Multi-voice** - Different voices for different moods/contexts
- **Voice-to-voice** - User sends voice message, bot responds with voice

---

## 📋 Checklist for New Characters

When adding voice to a new character:

1. [ ] Obtain/create ElevenLabs voice ID
2. [ ] Add `voice:` section to `ux.yaml`
3. [ ] Set `voice_id` in `ux.yaml` or `.env.{character}`
4. [ ] Customize `intro_template` for character personality
5. [ ] Add character-specific `trigger_keywords` if needed
6. [ ] Set `enabled: true` when ready
7. [ ] Test with various prompt types

---

## Appendix: Sample ux.yaml Voice Configs

### Elena (Marine Biologist)

```yaml
voice:
  enabled: true
  voice_id: "EXAVITQu4vr4xnSDxMaL"  # Soft, warm female voice
  always_include: false
  trigger_keywords:
    - "tell me about"
    - "how did you feel"
    - "speak to me"
    - "cuéntame"
  intro_template: "🔊 *Elena takes a breath... her voice carries across the waves...*\n\n🌊✨ *Elena speaks...*"
```

### Marcus (Musician)

```yaml
voice:
  enabled: true
  voice_id: "pNInz6obpgDQGcFmaJgB"  # Warm male voice
  always_include: false
  trigger_keywords:
    - "sing to me"
    - "play something"
    - "your voice"
  intro_template: "🎵 *Marcus clears his throat... the melody begins...*\n\n🎸✨ *Marcus sings...*"
```

### NotTaylor (Parody - Disabled)

```yaml
voice:
  enabled: false  # Legal concerns with voice similarity
  # voice_id: null
  intro_template: "🎤 *I would definitely NOT sound like anyone famous...*"
```

---

**Document maintained by:** WhisperEngine Team  
**Last updated:** November 27, 2025
