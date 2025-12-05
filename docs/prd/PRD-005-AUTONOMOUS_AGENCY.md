# PRD-005: Autonomous Agency & Social Presence

**Status:** ✅ Implemented
**Owner:** Mark Castillo
**Created:** December 4, 2025
**Updated:** December 4, 2025

## Origin

> **How did this need emerge?** Users felt the bots were too "reactive"—only speaking when spoken to. To feel like real community members, they need to initiate interactions.

| Field | Value |
|-------|-------|
| **Origin** | User Feedback / Emergence Research |
| **Proposed by** | Mark Castillo |
| **Catalyst** | Observation that "lurking" bots feel more alive than "summoned" bots |

## Problem Statement
Current AI characters are passive. They wait for a user to mention them or DM them. This creates a "service" dynamic rather than a "social" dynamic. In a real community, members observe conversations, react with emojis, and jump in when they have something relevant to say, even if not explicitly addressed.

## User Stories
1.  **As a server member**, I want the bot to react to my funny message with an emoji so that I feel heard even without a text reply.
2.  **As a server member**, I want the bot to occasionally chime in on a topic it cares about (e.g., Elena on marine biology) so that it feels like a participant.
3.  **As a server admin**, I want to control where and how often bots speak so they don't become spammy.
4.  **As a researcher**, I want to see if bots develop unique social patterns based on their personalities (e.g., some lurk more, some post more).

## Functional Requirements

### 1. Channel Lurking (Passive Engagement)
- **Requirement:** Bots must read messages in allowed channels without being mentioned.
- **Mechanism:** `LurkDetector` evaluates message relevance against character interests.
- **Constraint:** Must have a confidence threshold (e.g., >0.8) to avoid spam.

### 2. Autonomous Reactions
- **Requirement:** Bots should be able to add emoji reactions to user messages.
- **Mechanism:** `ReactionAgent` analyzes sentiment and context to select appropriate emojis.
- **Constraint:** Rate limited to prevent reaction spam.

### 3. Goal-Driven Posting
- **Requirement:** Bots should initiate posts based on internal drives or goals.
- **Mechanism:** `PostingAgent` checks internal state/goals and decides to post content (e.g., a daily thought, a question).

### 4. Activity Orchestration
- **Requirement:** Coordinate multiple bots to prevent them from talking over each other.
- **Mechanism:** `ActivityOrchestrator` manages a "conch shell" or token system for channel access.

## Technical Components (Mapped to Roadmap)
- **E15:** Autonomous Server Activity (The core implementation of all above features)
- **E10:** Channel Observer (Precursor, now integrated)

## Success Metrics
- **Engagement Rate:** % of bot-initiated interactions that receive a user reply.
- **Lurk Accuracy:** % of "lurk" responses that users react positively to (vs. telling the bot to shut up).
- **Retention:** Increase in daily active users in channels where bots are active.

## Privacy & Safety
- **Opt-In:** Lurking must be explicitly enabled per channel.
- **Quiet Hours:** Bots should respect server quiet hours.
- **Feedback Loop:** Users can tell a bot to "stop" or "go away," which should immediately lower its engagement probability.
