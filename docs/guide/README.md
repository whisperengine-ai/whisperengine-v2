# How-To Guides (GUIDE)

**Purpose:** Practical, task-oriented documentation that helps users and developers accomplish specific goals. These are the "how to use it" documents.

---

## Document Index

### User Guides

| GUIDE | Name | Audience | Description |
|-------|------|----------|-------------|
| [GUIDE-001](./GUIDE-001-TRUST_SYSTEM.md) | Trust System | Users | Understanding relationship progression |
| [GUIDE-002](./GUIDE-002-KNOWLEDGE_GRAPH.md) | Knowledge Graph | Users | How the bot remembers facts about you |
| [GUIDE-003](./GUIDE-003-USER_PREFERENCES.md) | User Preferences | Users | Customizing bot behavior |
| [GUIDE-004](./GUIDE-004-DREAMS_DIARIES.md) | Dreams & Diaries | Users | Character inner life and artifacts |
| [GUIDE-005](./GUIDE-005-COMMON_GROUND.md) | Common Ground | Users | Shared interest detection |

### Developer Guides

| GUIDE | Name | Audience | Description |
|-------|------|----------|-------------|
| [GUIDE-010](./GUIDE-010-IMAGE_GENERATION.md) | Image Generation | Developers | Image generation workflow |
| [GUIDE-011](./GUIDE-011-THINKING_INDICATORS.md) | Thinking Indicators | Developers | UX for processing states |
| [GUIDE-012](./GUIDE-012-REFLECTIVE_MODE.md) | Reflective Mode Controls | Developers | Configuring System 2 reasoning |
| [GUIDE-013](./GUIDE-013-CHARACTER_GOALS.md) | Character Goals | Developers | Goal system configuration |
| [GUIDE-014](./GUIDE-014-USER_IDENTIFICATION.md) | User Identification | Developers | Group chat user handling |

### Character Development

| GUIDE | Name | Audience | Description |
|-------|------|----------|-------------|
| [GUIDE-020](./GUIDE-020-CREATING_CHARACTERS.md) | Creating Characters | Developers | Full character creation guide |
| [GUIDE-021](./GUIDE-021-CHARACTER_EVOLUTION.md) | Character Evolution | Developers | Evolution and traits system |

---

## GUIDE Format Template

```markdown
# GUIDE-NNN: Task Name

**Audience:** Users | Developers | Admins
**Difficulty:** Beginner | Intermediate | Advanced
**Time:** ~X minutes
**Prerequisites:** [what you need to know first]

---

## Overview
What you'll learn and accomplish in this guide.

## Prerequisites
- Required knowledge
- Required setup
- Required access/permissions

## Steps

### Step 1: [Action]
Explanation of what to do.

```bash
# Example command or code
```

### Step 2: [Action]
...

## Verification
How to confirm you did it correctly.

## Common Issues

### Issue: [Problem]
**Symptom:** What you see
**Cause:** Why it happens
**Solution:** How to fix it

## Next Steps
What to learn or do next.

## Related Guides
- Links to related GUIDEs
```

---

## Relationship to Other Docs

| Doc Type | Purpose | Location |
|----------|---------|----------|
| **GUIDE** | How to use it (tutorials) | `docs/guide/` |
| **REF** | How it works (system docs) | `docs/ref/` |
| **SPEC** | How to build it (implementation) | `docs/spec/` |
| **PRD** | What & Why (user perspective) | `docs/prd/` |
| **ADR** | Why we chose X (decisions) | `docs/adr/` |
| **RUN** | How to operate it (runbooks) | `docs/run/` |

---

## Naming Convention

`GUIDE-NNN-{TASK_NAME}.md`

- **Number**: 001-009 user guides, 010-019 developer, 020+ specialized
- **Task name**: SCREAMING_SNAKE_CASE
- Examples:
  - `GUIDE-001-TRUST_SYSTEM.md`
  - `GUIDE-020-CREATING_CHARACTERS.md`
