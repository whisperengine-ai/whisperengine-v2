# Discord Bot Setup Guide

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Onboarding documentation |
| **Proposed by** | Mark (setup process) |

---

This guide covers creating a Discord application, configuring permissions, and inviting your WhisperEngine bot to servers.

## 1. Create Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application**
3. Name it (e.g., "Elena", "Marcus", etc.)
4. Go to **Bot** section → Click **Add Bot**

### Bot Settings

In the Bot section, configure:

| Setting | Value | Why |
|---------|-------|-----|
| **Public Bot** | Off (recommended) | Prevents random servers from adding your bot |
| **Requires OAuth2 Code Grant** | Off | Not needed |
| **Presence Intent** | On | Track user online status (for proactive messaging) |
| **Server Members Intent** | On | Access member list |
| **Message Content Intent** | On | **Required** - Read message content for conversations |

### Get Your Bot Token

1. In the Bot section, click **Reset Token**
2. Copy the token
3. Add to your `.env.botname` file:
   ```
   DISCORD_TOKEN=your_token_here
   DISCORD_BOT_NAME=botname
   ```

⚠️ **Never commit tokens to git!**

---

## 2. Bot Permissions

WhisperEngine bots require these permissions to function:

### Required Permissions (Core)

| Permission | Purpose |
|------------|---------|
| **View Channels** | See channels the bot can interact in |
| **Send Messages** | Reply to users |
| **Read Message History** | Context for conversations, fetching replied messages |
| **Embed Links** | Rich embeds for `/profile`, `/debug`, status displays |
| **Attach Files** | Send images (if vision/image features enabled) |
| **Add Reactions** | React to user messages with emoji |

### Optional Permissions (Feature-Dependent)

| Permission | Purpose | When Needed |
|------------|---------|-------------|
| **Manage Messages** | Delete spam messages | If spam detection with `delete` action enabled |
| **Connect** | Join voice channels | If voice features are used |
| **Speak** | Text-to-speech in voice channels | If voice features are used |

### Permission Integer

**Recommended (all features):** `3271616`

<details>
<summary>How this is calculated</summary>

| Permission | Bit Value |
|------------|-----------|
| View Channels | 1024 |
| Send Messages | 2048 |
| Manage Messages | 8192 |
| Embed Links | 16384 |
| Attach Files | 32768 |
| Read Message History | 65536 |
| Add Reactions | 64 |
| Connect | 1048576 |
| Speak | 2097152 |
| **Total** | **3271616** |

</details>

**Minimal (no voice, no spam deletion):** `117824`

<details>
<summary>Minimal calculation</summary>

| Permission | Bit Value |
|------------|-----------|
| View Channels | 1024 |
| Send Messages | 2048 |
| Embed Links | 16384 |
| Attach Files | 32768 |
| Read Message History | 65536 |
| Add Reactions | 64 |
| **Total** | **117824** |

</details>

---

## 3. Generate Invite URL

### Option A: Manual URL Construction

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3271616&scope=bot%20applications.commands
```

Replace `YOUR_CLIENT_ID` with your Application ID (found in General Information).

### Option B: OAuth2 URL Generator

1. Go to **OAuth2** → **URL Generator** in the Developer Portal
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions (or paste `3271616` in the permissions field)
4. Copy the generated URL

---

## 4. Invite Bot to Server

1. Open the invite URL in a browser
2. Select the server (you need Manage Server permission)
3. Review permissions and click **Authorize**
4. Complete the CAPTCHA

---

## 5. Verify Setup

After inviting, run these checks:

### In Discord
1. The bot should appear in the member list (may be offline until started)
2. Type `/` - you should see the bot's slash commands

### Start the Bot
```bash
./bot.sh up elena  # or your bot name
```

### Check Logs
```bash
./bot.sh logs elena -f
```

Look for:
```
✅ Guild 'Your Server': All required permissions granted
```

If you see missing permissions, update the bot's role in Server Settings → Roles.

### Test Commands
- `/elena ping` - Should respond with latency
- `/elena debug` - Should show bot configuration

---

## 6. Slash Command Sync

Slash commands sync automatically on bot startup. If commands don't appear:

1. Wait 1-2 minutes (Discord caches commands)
2. Try restarting Discord client
3. Check bot logs for sync errors

For development, commands sync to all guilds. For production, consider guild-specific sync for faster updates.

---

## Troubleshooting

### "Missing Access" Errors
- Bot lacks **View Channels** permission for that channel
- Check channel-specific permission overwrites

### "Missing Permissions" Errors
- Bot role is below the target in role hierarchy
- Re-invite with correct permissions or manually adjust role

### Slash Commands Not Showing
- Ensure `applications.commands` scope was included in invite
- Wait for Discord's command cache to refresh (up to 1 hour globally)
- Check bot logs for registration errors

### Voice Not Working
- Ensure **Connect** and **Speak** permissions
- Check if bot is being rate-limited (too many connect/disconnect cycles)

---

## Multi-Bot Setup

For multiple bots (elena, marcus, dotty, etc.):

1. Create separate Discord applications for each
2. Each gets its own token in `.env.botname`
3. Each can be invited to the same or different servers
4. Use the same permission integer (`3271616`) for all

See [MULTI_BOT_DEPLOYMENT.md](./MULTI_BOT_DEPLOYMENT.md) for infrastructure setup.

---

## Quick Reference

| Item | Value |
|------|-------|
| Permission Integer (Full) | `3271616` |
| Permission Integer (Minimal) | `117824` |
| Required Scopes | `bot`, `applications.commands` |
| Required Intents | Presence, Server Members, Message Content |
| Invite URL Template | `https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=3271616&scope=bot%20applications.commands` |
