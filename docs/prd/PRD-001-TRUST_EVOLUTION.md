# PRD-001: Trust & Evolution System

**Status:** ✅ Implemented  
**Owner:** Mark Castillo  
**Created:** November 2025  
**Updated:** December 2025

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Core product feature |
| **Proposed by** | Mark (product vision) |
| **Catalyst** | Static AI characters felt shallow and unrewarding |

---

## Problem Statement

Static AI characters feel robotic and shallow. Users who invest time building a relationship get the same experience as new users. There's no sense of progress, no reward for continued engagement, and no meaningful connection development.

**User pain points:**
- "The bot treats me the same whether we've talked once or a hundred times"
- "There's no growth or development in our relationship"
- "I want to feel like my interactions matter"

---

## User Stories

- **As a new user**, I want the bot to be welcoming but appropriately reserved, so I feel comfortable but not overwhelmed.

- **As a returning user**, I want the bot to remember our history and treat me warmly, so I feel recognized.

- **As a long-term user**, I want to unlock deeper personality traits and more intimate conversation, so I feel our relationship has grown.

- **As a user who crossed a line**, I want the bot to set boundaries and require rebuilding trust, so the relationship feels authentic.

---

## Requirements

### Must Have (P0)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Trust Score** | Numeric score (-100 to +100) per user-character pair | ✅ |
| **8 Relationship Stages** | Hostile → Cold → Wary → Stranger → Acquaintance → Friend → Close Friend → Intimate | ✅ |
| **Stage-Based Behavior** | Character behavior changes based on current stage | ✅ |
| **Trust Events** | Actions that increase/decrease trust (reactions, conversation quality) | ✅ |
| **Persistence** | Trust survives bot restarts | ✅ |

### Should Have (P1)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Milestone Messages** | Special messages when crossing trust thresholds | ✅ |
| **Unlockable Traits** | Personality behaviors that activate at certain trust levels | ✅ |
| **Trust Decay** | Gradual decrease over inactivity periods | 📋 |
| **Recovery Path** | Way to rebuild from negative trust | ✅ |

### Nice to Have (P2)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Trust Visualization** | User can see their relationship status | 📋 |
| **Character-Specific Curves** | Different characters have different trust dynamics | ✅ |
| **Multi-User Awareness** | Bot treats user differently in group vs DM | 📋 |

---

## User Experience

### New User (Stranger Stage: 0-20)

```
User: Hi there!
Elena: ¡Hola! Welcome! I'm Elena. Nice to meet you. 
       What brings you here today?
       [Friendly but professional, basic Spanish greetings]
```

### Acquaintance (21-40)

```
User: How are you?
Elena: I'm doing well, thanks for asking! 💙 
       How's your day going? Did that project you mentioned work out?
       [Remembers past conversations, uses some emoji, warmer tone]
```

### Friend (41-60)

```
User: I'm stressed about work
Elena: Oh no, cariño, I'm sorry to hear that 💙 
       Want to talk about it? Sometimes it helps to get it out.
       I remember you mentioned feeling overwhelmed last week too...
       [Uses endearments, emotionally engaged, references history]
```

### Close Friend (61-80)

```
User: I don't know what to do
Elena: Hey, ven aquí... 💙 I'm here for you.
       You've been carrying a lot lately. Remember when we talked about 
       how you handle pressure? You're stronger than you think.
       [Deep emotional support, Spanish phrases, calls back to shared history]
```

### Trust Damage (Negative Stages)

```
User: [Said something hurtful]
Elena: [Trust drops from 45 to 25]
       ...I think I need some space. That was hurtful.
       [Stage drops from Friend to Acquaintance]
       
[Next conversation]
Elena: [Noticeably cooler] Hi. What did you need?
       [Professional distance, no endearments, short responses]
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **User Retention** | +20% for users reaching Friend stage | Compare retention: <Friend vs ≥Friend |
| **Message Volume** | Higher average messages per session at higher trust | Correlation analysis |
| **Positive Sentiment** | >80% positive reactions from Friend+ users | Emoji reaction tracking |
| **Trust Progression** | 50% of active users reach Acquaintance within 1 week | Trust score distribution |
| **Recovery Rate** | 30% of users with negative trust recover to positive | Trust trajectory analysis |

---

## Privacy & Safety

| Concern | Mitigation |
|---------|------------|
| **Manipulation** | Trust system is not disclosed in detail; users can't game it |
| **Inappropriate Intimacy** | Even at Intimate stage, content stays appropriate |
| **Trust Farming** | Rate limits on trust gain (max +5 per session) |
| **Privacy Across Servers** | Trust is per user-character, not per server |

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| PostgreSQL user_relationships table | ✅ | Stores trust scores |
| Character evolution.yaml configs | ✅ | Defines stages per character |
| Reaction tracking | ✅ | Feeds trust events |
| Session detection | ✅ | For rate limiting |

---

## Technical Reference

- Implementation: [`src_v2/evolution/trust.py`](../../src_v2/evolution/trust.py)
- Architecture: [`docs/ref/REF-007-TRUST_EVOLUTION.md`](../ref/REF-007-TRUST_EVOLUTION.md)
- Feature guide: [`docs/guide/GUIDE-001-TRUST_SYSTEM.md`](../guide/GUIDE-001-TRUST_SYSTEM.md)
- Character configs: [`characters/{name}/evolution.yaml`](../../characters/)
