# Runbooks (RUN)

**Purpose:** Operational documentation for deploying, maintaining, and troubleshooting WhisperEngine. These are the "how to operate it" documents.

---

## Document Index

### Deployment

| RUN | Name | Description |
|-----|------|-------------|
| [RUN-001](./RUN-001-DEPLOYMENT.md) | Infrastructure Deployment | Setting up the full stack |
| [RUN-002](./RUN-002-MULTI_BOT.md) | Multi-Bot Deployment | Running multiple bots |
| [RUN-003](./RUN-003-DISCORD_SETUP.md) | Discord Bot Setup | Creating and configuring Discord bots |

### Operations

| RUN | Name | Description |
|-----|------|-------------|
| [RUN-010](./RUN-010-DATABASE_OPERATIONS.md) | Database Operations | Migrations, backups, recovery |
| [RUN-011](./RUN-011-MONITORING.md) | Monitoring & Alerting | Grafana, InfluxDB, health checks |
| [RUN-012](./RUN-012-TROUBLESHOOTING.md) | Troubleshooting | Common issues and solutions |

### Maintenance

| RUN | Name | Description |
|-----|------|-------------|
| [RUN-020](./RUN-020-UPGRADES.md) | Upgrade Procedures | Upgrading WhisperEngine versions |
| [RUN-021](./RUN-021-BACKUP_RESTORE.md) | Backup & Restore | Data backup and recovery |

---

## RUN Format Template

```markdown
# RUN-NNN: Procedure Name

**Type:** Deployment | Operations | Maintenance | Emergency
**Frequency:** Once | Daily | Weekly | As-needed
**Duration:** ~X minutes
**Risk Level:** Low | Medium | High
**Rollback:** [Can this be undone?]

---

## Origin

> **Why was this runbook created?** Document the trigger—incident, new feature, or operational learning.

| Field | Value |
|-------|-------|
| **Origin** | [e.g., "Production incident", "New deployment", "Operational learning"] |
| **Proposed by** | [e.g., "Mark", "Claude (collaborative)", "On-call engineer"] |
| **Catalyst** | [What necessitated this procedure?] |

## Overview
What this runbook accomplishes.

## Prerequisites
- Required access
- Required tools
- Required state (e.g., "bot must be stopped")

## Pre-Flight Checks
- [ ] Check 1
- [ ] Check 2
- [ ] Check 3

## Procedure

### Step 1: [Action]
```bash
# Command to run
```
**Expected output:** What you should see
**If failed:** What to do

### Step 2: [Action]
...

## Verification
How to confirm success.

## Rollback Procedure
How to undo if something goes wrong.

## Post-Procedure
- [ ] Update documentation if needed
- [ ] Notify stakeholders
- [ ] Monitor for issues

## Troubleshooting

### Problem: [Symptom]
**Cause:** Why it happens
**Solution:** 
```bash
# Fix command
```

## Related Runbooks
- Links to related RUNs
```

---

## Relationship to Other Docs

| Doc Type | Purpose | Location |
|----------|---------|----------|
| **RUN** | How to operate it (runbooks) | `docs/run/` |
| **GUIDE** | How to use it (tutorials) | `docs/guide/` |
| **REF** | How it works (system docs) | `docs/ref/` |
| **SPEC** | How to build it (implementation) | `docs/spec/` |

---

## Naming Convention

`RUN-NNN-{PROCEDURE_NAME}.md`

- **Number**: 001-009 deployment, 010-019 operations, 020+ maintenance
- **Procedure name**: SCREAMING_SNAKE_CASE
- Examples:
  - `RUN-001-DEPLOYMENT.md`
  - `RUN-012-TROUBLESHOOTING.md`
