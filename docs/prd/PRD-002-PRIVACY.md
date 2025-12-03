# PRD-002: Privacy & Data Handling

**Status:** ✅ Implemented  
**Owner:** Mark Castillo  
**Created:** November 2025  
**Updated:** December 2025

---

## Problem Statement

AI chatbots that remember user information create privacy risks. Users share personal details in what they perceive as private contexts (DMs, private servers), but that information may surface in public contexts. Users need to understand what's stored, how it's used, and what control they have.

**User pain points:**
- "I said something private in a DM—will it come up in public?"
- "I don't know what the bot remembers about me"
- "I want to delete my data but don't know how"
- "I shared something in a private server, now it's being referenced elsewhere"

---

## User Stories

- **As a privacy-conscious user**, I want to understand what data is collected, so I can make informed decisions about what I share.

- **As a user in multiple servers**, I want my conversations in one server to stay in that context, so I'm not surprised by cross-server references.

- **As a user who overshared**, I want to delete specific information the bot learned about me, so I can correct mistakes.

- **As a server admin**, I want to understand how user data is handled in my server, so I can inform my members.

---

## Requirements

### Must Have (P0)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Data Transparency** | Clear documentation of what's stored | ✅ |
| **Chat History Segmentation** | Raw messages stay within their channel context | ✅ |
| **User ID as Identifier** | Single profile per Discord user across all contexts | ✅ |
| **No DMs for General Users** | DMs disabled to prevent false privacy expectations | ✅ |

### Should Have (P1)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Privacy Command** | `/privacy` command to see what's stored | 📋 |
| **Fact Deletion** | User can request removal of specific facts | ✅ |
| **Context Warning** | Bot warns when recalling cross-context info | 📋 |
| **Opt-Out Options** | User can disable certain data collection | 📋 |

### Nice to Have (P2)

| Requirement | Description | Status |
|-------------|-------------|--------|
| **Data Export** | User can request export of all their data | 📋 |
| **Retention Policies** | Automatic deletion after inactivity period | 📋 |
| **Server-Scoped Mode** | Option for servers to keep data isolated | 📋 |

---

## Data Handling by Type

### Chat Messages (PostgreSQL) — ✅ Segmented

| Aspect | Behavior |
|--------|----------|
| **Storage** | `v2_chat_history` table |
| **Segmentation** | By channel_id; messages in #general don't appear in #private history |
| **Cross-Context** | ❌ Not shared between channels |
| **Retention** | Indefinite (no auto-delete) |

### Vector Memories (Qdrant) — ⚠️ User-Global

| Aspect | Behavior |
|--------|----------|
| **Storage** | Qdrant collection `whisperengine_memory_{bot_name}` |
| **Segmentation** | ❌ Per-user only, not per-channel or per-server |
| **Cross-Context** | ⚠️ Memories from any context can surface anywhere |
| **Risk** | Private DM content can surface in public channels |

### Knowledge Facts (Neo4j) — ⚠️ User-Global

| Aspect | Behavior |
|--------|----------|
| **Storage** | Neo4j graph nodes and relationships |
| **Segmentation** | ❌ Per-user only, not per-context |
| **Cross-Context** | ⚠️ Facts from any context are globally accessible |
| **Risk** | "I'm Sarah, 28, in Seattle with depression" from private server → public |

### Trust & Preferences (PostgreSQL) — Per User-Character

| Aspect | Behavior |
|--------|----------|
| **Storage** | `v2_user_relationships` table |
| **Segmentation** | Per user-character pair (not per server) |
| **Cross-Context** | Trust score is same across all servers |

---

## User Experience

### Privacy Warning (Shown in docs/commands)

```
⚠️ PRIVACY NOTICE

This bot uses your Discord User ID as a global identifier. 
Information shared in ANY context (public channels, private channels, 
different servers) is stored in a unified profile.

What this means:
• Information from private channels CAN appear in public interactions
• Information from Server A CAN appear when talking in Server B
• DMs are disabled to prevent false expectations of privacy

To see what's stored: /mydata
To delete a fact: /forget "fact to remove"
```

### Cross-Context Warning (When referencing private info publicly)

```
User (in public #general): How are you?
Elena: [About to reference private health info]
       
       [Internal check: source_context != current_context]
       [Decide: reference with caution or omit]
       
Elena: I'm well! How about you? 
       [Omits private health reference in public context]
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Privacy Complaints** | <5% of users report privacy concerns | User feedback tracking |
| **Data Deletion Requests** | <10% of active users request deletions | Request volume |
| **Cross-Context Incidents** | 0 reported incidents of sensitive info leakage | Incident reports |
| **Documentation Reach** | 50% of active users have seen privacy docs | Command/page views |

---

## Privacy & Safety

| Risk | Mitigation | Status |
|------|------------|--------|
| **Sensitive Info in Public** | Context-aware response filtering | 📋 Proposed |
| **Cross-Server Leakage** | Trust-gated information sharing | ✅ |
| **No User Control** | Deletion commands, privacy dashboard | 🔄 Partial |
| **Unclear Data Practices** | Comprehensive documentation | ✅ |

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| PostgreSQL data storage | ✅ | Chat history, relationships |
| Qdrant memory storage | ✅ | Vector memories |
| Neo4j fact storage | ✅ | Knowledge graph |
| Privacy Manager | ✅ | `src_v2/core/privacy.py` |

---

## Technical Reference

- Privacy documentation: [`docs/PRIVACY_AND_DATA_SEGMENTATION.md`](../PRIVACY_AND_DATA_SEGMENTATION.md)
- Privacy manager: [`src_v2/core/privacy.py`](../../src_v2/core/privacy.py)
- Memory manager: [`src_v2/memory/manager.py`](../../src_v2/memory/manager.py)
- Knowledge manager: [`src_v2/knowledge/manager.py`](../../src_v2/knowledge/manager.py)
