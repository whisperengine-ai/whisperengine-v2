# DM Blocking & Privacy Controls

## Overview

WhisperEngine v2 includes a strict **Direct Message (DM) Blocking** system enabled by default. This feature is designed to enforce privacy by design, preventing users from assuming that DMs with the bot are private conversations.

## Why Block DMs?

As detailed in [Privacy & Data Segmentation](../PRIVACY_AND_DATA_SEGMENTATION.md), the bot maintains a **unified global profile** for each user. Information shared in DMs is:
1. Stored in the global vector memory
2. Accessible to the bot in public channels
3. Used to extract facts that become part of the user's global knowledge graph

By blocking DMs, we:
- **Prevent accidental leakage** of sensitive information
- **Set clear expectations** that all bot interactions are public/visible
- **Protect users** who might otherwise treat the bot as a confidant

## Configuration

This feature is controlled via environment variables in your `.env` file.

### Enable/Disable Blocking

```bash
# .env
# Default: True (Recommended for production)
ENABLE_DM_BLOCK=True
```

Set to `False` to allow DMs for everyone (not recommended for public bots).

### Allowlisting Users

You can allow specific users (e.g., Admins, Developers, Moderators) to bypass the block. This is useful for testing or administrative tasks.

```bash
# .env
# Comma-separated list of Discord User IDs
DM_ALLOWED_USER_IDS=123456789012345678,987654321098765432
```

**Note**: Even for allowlisted users, DMs are **NOT private**. The bot still stores all interactions in the global profile.

## User Experience

### Blocked Users
When a non-allowlisted user attempts to DM the bot, they receive an immediate embed response:

> **🚫 Direct Messages Disabled**
>
> For privacy reasons, I do not accept Direct Messages.
>
> This ensures all interactions happen in visible server contexts and prevents accidental sharing of sensitive information.
>
> Please interact with me in a server channel instead.

The bot **does not** process the message further, meaning:
- No memory is stored
- No LLM inference is triggered (saving costs)
- No facts are extracted

### Allowed Users
Users in `DM_ALLOWED_USER_IDS` experience normal bot behavior. The bot will:
- Respond to the message
- Store the conversation in memory
- Extract facts and preferences

## Best Practices for Admins

1. **Keep the Allowlist Small**: Only add users who strictly need DM access for debugging or administration.
2. **Don't Disable Globally**: Unless you are running a private, single-user instance, keep `ENABLE_DM_BLOCK=True`.
3. **Educate Users**: Use the server rules to explain that the bot is "public-only" for their safety.
