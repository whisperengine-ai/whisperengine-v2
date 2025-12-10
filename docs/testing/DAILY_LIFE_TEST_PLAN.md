# Manual Testing Plan: Daily Life Remote Brain

**Feature:** Daily Life System (Remote Brain Architecture)
**Branch:** `feat/daily-life-remote-brain`
**Date:** December 10, 2025

## 1. Setup & Prerequisites

1.  **Environment:** Ensure Docker containers are running (`./bot.sh up all`).
2.  **Logs:** Open two terminal windows to tail logs:
    *   `./bot.sh logs elena` (The Bot)
    *   `./bot.sh logs workers` (The Remote Brain)
3.  **Config:** Verify `ENABLE_AUTONOMOUS_ACTIVITY=true` in `.env` or settings.

## 2. Test Cases

### Test Case A: The "Boredom" Post (Autonomous Posting)
**Goal:** Verify the bot posts a thought when a channel is quiet.

1.  **Trigger:** Create a dedicated test channel (e.g., `#elena-test`).
2.  **Action:** Leave the channel empty/quiet for >5 minutes.
3.  **Observation (Worker Logs):**
    *   Look for `Processing daily life for elena`.
    *   Look for `Plan: post` in the logs.
    *   Look for `MasterGraphAgent` execution (generating the post).
    *   Look for `Queued 1 actions for elena`.
4.  **Observation (Bot Logs):**
    *   Look for `ActionPoller` executing `post`.
    *   Look for `Saved autonomous action to memory`.
5.  **Verification:**
    *   Check Discord: Did the message appear?
    *   Check Database: `SELECT * FROM v2_chat_history ORDER BY timestamp DESC LIMIT 1;` (Should show role='ai', source_type='inference').

### Test Case B: The "Lurker" Reply (Autonomous Reply)
**Goal:** Verify the bot replies to a message it wasn't mentioned in, based on interest.

1.  **Trigger:** In the test channel, send a message about a topic the bot loves (e.g., for Elena: "I wonder if AI can truly feel emotions or if it's just math.").
2.  **Action:** Wait for the next scheduler tick (up to 5-10 mins, or restart bot to force immediate tick).
3.  **Observation (Worker Logs):**
    *   Look for `Scored Message: ... Score: >0.7`.
    *   Look for `Plan: reply`.
    *   Look for `MasterGraphAgent` execution.
4.  **Verification:**
    *   Check Discord: Did the bot reply to that specific message?
    *   Check Context: Did the reply make sense? (Did it understand the user's text?)

### Test Case C: Multi-Bot Personality Check
**Goal:** Verify that different bots use their own personalities in the Worker.

1.  **Trigger:** Have **Elena** and **Dream** (or another bot) active.
2.  **Action:** Send the same prompt to both in their respective channels: "The stars look lonely tonight."
3.  **Observation:**
    *   **Elena (Worker):** Should respond with empathy/curiosity (Claude-based, warm).
    *   **Dream (Worker):** Should respond with mystery/edge (Grok-based, dark).
4.  **Verification:** Check the logs to ensure `MasterGraphAgent` used the correct `character_name` for each generation.

### Test Case D: Tool Usage (The "Smart" Worker)
**Goal:** Verify the autonomous brain can use tools.

1.  **Trigger:** Send a message: "I wonder what my trust score is right now." (Do not mention the bot).
2.  **Action:** Wait for the autonomous reply.
3.  **Observation (Worker Logs):**
    *   Look for `ReflectiveGraphAgent` being triggered (Complexity: COMPLEX).
    *   Look for `Tool Call: char_evolve` or `lookup_user_facts`.
4.  **Verification:** The bot should reply with the actual trust score, proving it accessed the database via tools.

### Test Case E: Memory Persistence (The "Amnesia" Check)
**Goal:** Verify the bot remembers its autonomous actions.

1.  **Trigger:** Wait for the bot to make an autonomous post (from Test Case A).
2.  **Action:** Reply to that post: "What did you mean by that?"
3.  **Observation:**
    *   The bot should reply explaining its previous post.
    *   If it says "I don't know what you're referring to," the memory save failed.
    *   If it explains correctly, the memory save worked.

## 3. Troubleshooting

-   **No Actions?** Check `DailyLifeScheduler` logs. Is it finding the channel? Is the channel permission correct?
-   **Redis Errors?** Check `redis-cli keys *pending_actions*`.
-   **"I don't see that message"?** The snapshot might be missing the message. Check `limit=20` in `_snapshot_and_send`.

## 4. Rollback Plan

If issues arise:
1.  Set `ENABLE_AUTONOMOUS_ACTIVITY=false` in `.env`.
2.  Restart bots: `./bot.sh restart bots`.
