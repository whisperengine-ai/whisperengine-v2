# Discord Integration - The Sensory Interface

**Version**: 2.2  
**Last Updated**: December 1, 2025

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Platform integration |
| **Proposed by** | Mark (Discord architecture) |
| **Key insight** | Discord is the gateway through which all external data flows |

---

## Multi-Modal Context: Discord as Input System

Discord is the **input interface** through which characters receive all external data. Every message, reaction, voice channel, and image comes through Discord's events.

| Discord Event | Input Modality |
|---------------|---------------------|
| `on_message` (text) | 💬 Text input |
| `on_message` (with image) | 👁️ Vision input |
| `on_voice_state_update` | 👂 Audio input |
| `on_reaction_add` | ❤️ Emotion input |
| Channel presence | 🌌 Universe (spatial awareness) |
| User activity | 🌌 Universe (social awareness) |

Discord is the gateway through which all external data flows into the system.

For full philosophy: See [`MULTI_MODAL_PERCEPTION.md`](./MULTI_MODAL_PERCEPTION.md)

---

WhisperEngine v2 uses `discord.py` to interface with the Discord API. The bot is designed to be "channel-aware" and supports both text and voice interactions.

## Architectural Theory: Event-Driven & Proactive Agents

### Reactive vs. Proactive
Traditional chatbots are **Reactive**: they only speak when spoken to (Request-Response).
WhisperEngine v2 is **Proactive**: it has its own internal clock and agenda.

*   **Event-Driven**: The system reacts to external events (`on_message`, `on_voice_state_update`).
*   **Agentic Loop**: A background scheduler acts as the character's "Subconscious," checking if it should initiate a conversation based on time of day, past interactions, or "epiphanies" (simulated thoughts).

### Message Lifecycle Diagram

```mermaid
sequenceDiagram
    participant User
    participant Discord
    participant Bot as WhisperBot
    participant Engine as AgentEngine
    participant TTS as VoiceService
    
    User->>Discord: Sends Message
    Discord->>Bot: on_message(event)
    
    Bot->>Bot: Check Filters (Self, Bots)
    Bot->>Bot: Determine Intent (DM vs Mention)
    
    rect rgb(240, 240, 240)
        Note over Bot: Processing
        Bot->>Discord: Send Typing Indicator
        Bot->>Engine: generate_response(msg, history)
        Engine-->>Bot: "Hello there!"
    end
    
    par Text Response
        Bot->>Discord: Send Message "Hello there!"
        Discord->>User: Display Message
    and Voice Response (If in VC)
        Bot->>TTS: Synthesize("Hello there!")
        TTS-->>Bot: Audio Stream
        Bot->>Discord: Play Audio
        Discord->>User: Hear Audio
    end
```

## Autonomy Architecture: The Stream & The Reverie

WhisperEngine v2.5 implements a **Hybrid Autonomy Model**:

### A. The Stream (Real-time Nervous System)
Instead of just polling every 7 minutes, the bot has a "Nervous System" that reacts immediately to high-signal events.
*   **Triggers:** Trusted users (Level 4+), Watchlist channels.
*   **Mechanism:** `on_message` -> `trigger_immediate()` -> Redis Debounce (60s) -> Focused Snapshot.
*   **Benefit:** The bot feels "alive" and responsive to its friends without spamming every channel.

### B. The Reverie (Active Idle State)
When the server is silent, the bot enters an introspective state.
*   **Trigger:** Silence > 2 hours (configurable).
*   **Mechanism:** `DailyLifeScheduler` -> `run_reverie_cycle`.
*   **Process:** The bot retrieves recent memories, finds connections in the Knowledge Graph, and generates "Synthetic Memories" (insights) to bridge them.
*   **Benefit:** The bot develops its own internal life and self-model even without user interaction.

> **Note:** This is distinct from the **Dream Journal**, which is a scheduled daily task that broadcasts a narrative to the user. Reverie is invisible background maintenance.

## Core Components

### 1. `WhisperBot` (`src_v2/discord/bot.py`)
The main bot class inheriting from `commands.Bot`.

**Key Responsibilities:**
*   **Event Loop**: Handles `on_ready`, `on_message`.
*   **Status Updates**: Periodically updates the "Playing..." status with stats (friend count, memories).
*   **Message Chunking**: Splits long responses (>2000 chars) into multiple messages.
*   **Daily Life Scheduler**: Manages the background autonomy loop (polling + dreaming).

### 2. Message Handling Flow

1.  **Trigger Detection**:
    *   **Direct**: DM or Mention -> Respond immediately.
    *   **Stream Trigger**: Trusted User or Watchlist Channel -> **Immediate Snapshot** (bypasses poll).
    *   **Autonomous**: Periodic Poll (7 mins) -> Check for relevant conversations.

2.  **Processing**:
    *   **Typing Indicator**: `async with message.channel.typing():` is used to show the bot is "thinking".
    *   **Context Gathering**: Fetches recent channel history.
    *   **Engine Call**: Passes the message to `AgentEngine`.

3.  **Response**:
    *   **Text**: Sent back to the channel.
    *   **Voice**: If in a voice channel, the text is also sent to the TTS engine.

### 3. Voice Architecture (`src_v2/discord/voice.py`)

*   **Voice Client**: Manages the connection to a Discord voice channel.
*   **Audio Source**: Uses `FFmpegPCMAudio` to stream generated audio.
*   **TTS Integration**:
    *   Text response -> TTS Service (ElevenLabs/OpenAI) -> MP3 File.
    *   MP3 File -> FFmpeg -> Discord Voice Stream.

### 4. Commands (`src_v2/discord/commands.py`)

Slash commands for managing the bot.

*   `/reset`: Clears the current session context.
*   `/memory query:{text}`: Debug command to search vector memory.
*   `/upload`: Upload a file for the bot to "read" (ingest into knowledge base).
*   `/join`: Join the user's voice channel.
*   `/leave`: Leave the voice channel.

## Proactive Messaging (Daily Life System)

The bot isn't just reactive. It can initiate conversations based on:
*   **Time**: "Good morning" messages.
*   **Events**: "I just remembered..." (Epiphanies).
*   **Inactivity**: "Hey, haven't heard from you in a while."

**Mechanism (Daily Life Graph)**:
*   `DailyLifeScheduler` periodically snapshots channel activity and sends to the worker.
*   The worker's Remote Brain agent decides on autonomous actions (posts, reactions).
*   `ActionPoller` polls Redis for action instructions and executes them.
*   See `src_v2/discord/daily_life.py` for implementation.
