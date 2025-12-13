# Project Report: Autonomous Behavior Refinement

**Date:** December 11, 2025
**Status:** In Progress

## 1. Overview
Following the implementation of "The Stream" (Phase 2.5.2), we focused on refining the autonomous behavior to be more natural, less spammy, and socially aware.

## 2. Key Improvements

### A. Social Battery Implementation
- **Mechanism**: Wired up the `DriveManager` to the `DailyLifeGraph`.
- **Drain**: Proactive actions (posts) drain battery faster (-0.15) than reactive ones (-0.05).
- **Recharge**: Passive conversation recharges battery (+0.02 per message).
- **Effect**: When battery is low (< 0.2), the bot enters "Recharge Mode" and stops proactive posting, only replying when spoken to.
- **Configuration**: Added `social_battery_limit` to all 12 character profiles.

### B. Threaded Replies for Proactive Reach-Outs
- **Problem**: Bots were always posting new messages even when "reaching out" to an active conversation, breaking the flow.
- **Solution**: Modified `DailyLifeGraph` (`reach_out` intent) to:
    1. Scan the target channel for the most recent message.
    2. If a message exists (and isn't from the bot itself), target it.
    3. Use Discord's "Reply" feature (via `ActionCommand` with `target_message_id`).
- **Result**: Proactive interactions now visually link to the conversation context, creating natural threads.

### C. Self-Reply Loop Prevention
- **Logic**: Added checks in `DailyLifeGraph` to ensure `reach_out` does not target the bot's own last message.
- **Fallback**: If the only recent messages are from the bot itself, it defaults to a new post instead of a reply.

### D. Raw Tool Output Fix
- **Issue**: Bots were occasionally outputting raw JSON tool calls in the "Fast Path" (direct LLM response).
- **Fix**: Modified `context_builder.py` and `master_graph.py` to conditionally hide tool instructions from the system prompt when tools are not bound to the model.

## 3. Files Modified
- `src_v2/agents/daily_life/graph.py`: Added reply logic and battery drain.
- `src_v2/discord/daily_life.py`: Added support for `target_message_id` in `ActionCommand`.
- `src_v2/discord/handlers/message_handler.py`: Added battery recharge logic.
- `characters/*/core.yaml`: Updated configuration.

## 4. Next Steps
- Monitor behavior in production (Nottaylor) to tune battery drain/recharge rates.
- Verify "Stream" triggers are working as expected with the new battery constraints.
