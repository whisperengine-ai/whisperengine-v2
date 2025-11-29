# Code Review: Phase E6 (Character-to-Character Chat)

**Date:** November 28, 2025
**Reviewer:** GitHub Copilot
**Status:** ✅ Approved

## Summary
The implementation of Phase E6 enables organic cross-bot conversations while mitigating risks of infinite loops and spam. The architecture uses a centralized `CrossBotManager` backed by Redis for service discovery and in-memory state for conversation tracking.

## Key Components Reviewed

### 1. Configuration (`src_v2/config/settings.py`)
- **Settings Added:**
  - `ENABLE_CROSS_BOT_CHAT`: Feature flag (default: False)
  - `CROSS_BOT_MAX_CHAIN`: Limit of 3 replies (prevents loops)
  - `CROSS_BOT_COOLDOWN_MINUTES`: 10-minute cooldown per channel
  - `CROSS_BOT_RESPONSE_CHANCE`: 0.7 probability (adds organic feel)
- **Verdict:** Correctly typed and defaulted.

### 2. Logic Engine (`src_v2/broadcast/cross_bot.py`)
- **ConversationChain:**
  - Effectively tracks participants and message counts.
  - `should_continue` check enforces the `MAX_CHAIN` limit.
- **CrossBotManager:**
  - **Discovery:** Uses Redis (`crossbot:known_bots`) to dynamically discover other bots. This is robust for a multi-container deployment.
  - **Detection:**
    - Correctly ignores own messages.
    - Verifies the author is a "known bot" (security).
    - Checks for mentions OR name keywords.
  - **Safety:**
    - `is_on_cooldown` prevents channel spam.
    - `chain.last_bot == self._bot_name` check prevents self-reply loops.
- **Verdict:** Solid logic with good safety rails.

### 3. Discord Integration (`src_v2/discord/bot.py`)
- **Event Handling:**
  - `on_message` correctly routes bot messages to `_handle_cross_bot_message`.
  - `on_ready` initializes the manager and loads known bots.
- **Response Generation:**
  - Uses `force_fast=True` for the LLM, which is appropriate for banter (low latency/cost).
  - Injects specific `cross_bot_context` to guide the persona (playful, brief).
  - Adds artificial delay (2-5s) and typing indicator for realism.
- **Verdict:** Good UX and efficient resource usage.

## Recommendations
1.  **Redis Cleanup:** Currently, `crossbot:known_bots` has no expiration. If a bot is permanently removed, it remains "known". Consider adding a TTL or a cleanup job in the future.
2.  **Unused Queue Logic:** `queue_cross_bot_mention` exists in `CrossBotManager` but isn't used in the direct `on_message` flow. Ensure this is intended for future use (e.g., broadcast handling).

## Conclusion
The code is production-ready. The safety mechanisms (chain limits, cooldowns, probability) are sufficient to prevent runaway bot conversations.
