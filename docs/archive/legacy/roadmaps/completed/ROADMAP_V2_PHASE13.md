# Roadmap V2 - Phase 13: Proactive Engagement

This phase transforms the bot from a reactive responder into a proactive companion. It will analyze user activity patterns and initiate conversations at appropriate times.

## Goals
- [x] **Activity Modeling**: Analyze session history to determine "active hours" for each user.
- [x] **Proactive Scheduler**: Implement a background task to check for engagement opportunities.
- [x] **Engagement Triggers**: Define rules for *when* and *why* to message first (e.g., "Haven't spoken in 24h", "User usually active now").
- [x] **Topic Selection**: Use the Knowledge Graph to pick a relevant topic for the opening message.

## Tasks

### 1. Activity Analysis (`src_v2/intelligence/activity.py`)
- [x] Create `ActivityModeler` class.
- [x] Implement `get_user_activity_heatmap(user_id)`:
    - Queries `v2_conversation_sessions`.
    - Returns a 24x7 grid of activity probabilities.
- [x] Implement `is_good_time_to_message(user_id)`:
    - Checks current time against the heatmap.
    - Returns boolean + confidence score.

### 2. Proactive Scheduler (`src_v2/discord/scheduler.py`)
- [x] Create `ProactiveScheduler` class.
- [x] Implement `start_loop()`:
    - Runs every 15-60 minutes.
    - Iterates through active users.
- [x] Implement `check_user(user_id)`:
    - Checks `last_message_time`.
    - Checks `is_good_time_to_message`.
    - Checks `trust_score` (only message trusted users).

### 3. Message Generation (`src_v2/agents/proactive.py`)
- [x] Create `ProactiveAgent` class.
- [x] Implement `generate_opener(user_id)`:
    - Fetches recent memories and knowledge graph facts.
    - Generates a context-aware opening message (e.g., "How did that meeting go?").

### 4. Integration
- [x] Initialize `ProactiveScheduler` in `WhisperBot.setup_hook`.
- [x] Add configuration to enable/disable proactivity per character.

### 5. Privacy & Safety (Added)
- [x] Implement DM allowlist check to prevent messaging users who can't reply.
- [x] Add channel detection to ping users in public channels instead of DMs.
- [x] Implement multi-layer privacy protection for public channel messages:
  - [x] LLM instruction layer with explicit privacy warnings.
  - [x] Knowledge graph filtering to remove sensitive keywords.
  - [x] Context awareness flag (`is_public`) passed to agent.

### 6. Channel-Aware Context (Added)
- [x] Fetch channel-specific conversation history for public messages.
- [x] Implement "safe topics" inference from channel history.
- [x] Add unfinished conversation detection logic.
- [x] Pass channel_id to proactive agent for context-aware generation.

## Success Criteria
- [x] Bot sends a message to the user after 24h of silence, during their active hours.
- [x] The message references a previous topic or fact ("How is Luna doing?").
- [x] User responds positively (tracked via feedback).
- [x] Bot respects DM privacy settings and uses public channels when available.
- [x] Bot never reveals sensitive information in public channels.
- [x] Bot follows up on unfinished conversations from specific channels.

## Implementation Notes

### Architecture
- **Entry Point**: `ENABLE_PROACTIVE_MESSAGING` setting in `.env.{bot_name}`
- **Scheduler**: Runs every 60 minutes, checks all users with trust_score >= 20
- **Filters**: Trust, silence duration (24h), activity modeling, DM privacy
- **Channel Detection**: Queries last `channel_id` from `v2_chat_history`
- **Memory Persistence**: Saves sent messages to memory for continuity

### Privacy Architecture (Multi-Layer)
1. **Channel Preference**: Tries to use last public channel; falls back to DM
2. **DM Check**: Skips users not in `DM_ALLOWED_USER_IDS` when target is DM
3. **Knowledge Filtering**: Removes facts containing sensitive keywords (health, finance, etc.)
4. **LLM Instructions**: Explicit privacy warnings for public messages
5. **Channel Context**: Uses channel-specific history as "safe topics list"

### Key Features
- **Unfinished Conversation Detection**: Looks for questions left unanswered or topics left hanging
- **Channel-Specific Memory**: Fetches last 5 turns from the target channel
- **Safe Topic Inference**: Topics discussed publicly before are considered safe to reference again

### Configuration
```bash
# Enable proactive messaging
ENABLE_PROACTIVE_MESSAGING=true

# Optionally adjust DM privacy
ENABLE_DM_BLOCK=true
DM_ALLOWED_USER_IDS=123456789,987654321
```

### Tunable Parameters (in `scheduler.py`)
- `check_interval_minutes`: How often to check (default: 60)
- `min_trust_score`: Minimum trust to message (default: 20)
- `silence_threshold_hours`: Hours of silence before messaging (default: 24)
