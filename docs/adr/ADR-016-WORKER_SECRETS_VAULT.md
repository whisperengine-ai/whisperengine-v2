# ADR-016: Worker Secrets Vault & Generic Workers

**Status:** 📋 Proposed  
**Date:** 2024-12-13  
**Deciders:** Mark, Claude (collaborative)

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture discussion |
| **Proposed by** | Mark (insight about token sharing) |
| **Catalyst** | Autonomous features suspended due to multi-bot coordination problems; need cleaner worker architecture |

## Context

Autonomous features (Daily Life Graph, cross-bot coordination) were suspended because:

1. **N² event duplication**: Every bot processed every channel message
2. **Pile-on behavior**: Multiple bots responding to same message independently
3. **Workers can't send to Discord**: Current workers lack Discord tokens
4. **Gateway constraint**: Only ONE process can hold an active Discord gateway connection per token

We explored several options:
- Per-bot dedicated workers (with token in env file)
- Token in job payload (works for bot-initiated tasks only)
- Token via Redis vault (enables all patterns)

Key insight from Mark: **If workers get secrets from Redis, ANY worker can do ANY bot's work** — they just look up credentials based on `bot_name` in the job payload.

## Decision

Implement a **Redis-based secrets vault** with **generic workers** and **per-bot inboxes**:

### 1. Secrets Vault (Redis)

Bots publish their secrets to Redis on startup:

```python
# Bot process (on startup + periodic refresh)
await redis.hset(f"secrets:{bot_name}", mapping={
    "discord_token": token,
    "openai_api_key": settings.OPENAI_API_KEY,
    "anthropic_api_key": settings.ANTHROPIC_API_KEY,
    # ... other LLM keys
})
await redis.expire(f"secrets:{bot_name}", 86400)  # 24h TTL, bot refreshes
```

Workers read secrets on demand:

```python
class SecretsVault:
    async def get(self, bot_name: str, key: str) -> str:
        return await redis.hget(f"secrets:{bot_name}", key)

# Usage
vault = SecretsVault()
token = await vault.get("elena", "discord_token")
```

### 2. Generic Workers (Any Worker → Any Bot)

Workers are stateless and generic. Job payloads include `bot_name`:

```python
# Job payload
{
    "bot_name": "elena",
    "task": "process_channel_message",
    "channel_id": "123",
    "message_id": "456",
}

# Worker reads bot_name, fetches secrets, processes
async def process_task(job: dict):
    bot_name = job["bot_name"]
    token = await vault.get(bot_name, "discord_token")
    llm_key = await vault.get(bot_name, "anthropic_api_key")
    # ... process with correct credentials
```

### 3. Per-Bot Inboxes (Not Per-Bot Workers)

```
inbox:elena     →  Any worker can process
inbox:dotty     →  Any worker can process
inbox:aria      →  Any worker can process
```

Workers pull from all inboxes (or round-robin), look up secrets per job.

### 4. Bot = Gateway, Worker = Brain + REST

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Bot Process (elena)                             │
│                      Gateway Connection Only                         │
│                                                                      │
│  on_startup() ──► Push secrets to Redis vault                       │
│  on_message() ──► Is direct? ──YES──► Process immediately           │
│                       │                                              │
│                      NO (channel msg)                                │
│                       ▼                                              │
│              XADD inbox:elena {event}                                │
│              (fire and forget, ~1ms)                                 │
└─────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Redis                                           │
│                                                                      │
│   secrets:elena   {discord_token, openai_key, ...}                  │
│   secrets:dotty   {discord_token, openai_key, ...}                  │
│   inbox:elena     [event1, event2, ...]                             │
│   inbox:dotty     [event1, event2, ...]                             │
│   channel:123:recent_bot_posts  [elena@12:01, dotty@12:02]         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Generic Worker (any of N workers)                  │
│                                                                      │
│  Loop:                                                               │
│    1. XREAD from inbox:* (any bot's inbox)                          │
│    2. Extract bot_name from event                                    │
│    3. Fetch secrets: vault.get(bot_name, "discord_token")           │
│    4. Load character config for bot_name                             │
│    5. Should I respond? (LLM / heuristics)                          │
│    6. Check coordination: channel:{id}:recent_bot_posts             │
│    7. If yes: Generate response (LLM with bot's key)                │
│    8. Send via Discord REST API (with bot's token)                  │
│    9. Record: ZADD channel:{id}:recent_bot_posts bot_name {ts}      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5. Discord REST API (No Gateway Conflict)

Workers use REST API, not gateway. Same token works for both:

```python
# Gateway (bot process) — persistent WebSocket, only one allowed
bot.run(token)

# REST API (worker process) — stateless HTTP, unlimited
async def send_message(channel_id: str, content: str, token: str):
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": content}
        )
```

No conflict — bot holds gateway, workers use REST.

## Consequences

### Positive

1. **Workers are generic**: Scale horizontally without per-bot configuration
2. **Single source of truth**: Secrets only in `.env.{bot}`, published to Redis
3. **No env files for workers**: Workers only need `REDIS_URL`
4. **Dynamic credential rotation**: Change token, restart bot, workers auto-update
5. **Solves gateway constraint**: Workers use REST, no conflict with bot's gateway
6. **Enables autonomous features**: Workers can now send to Discord directly
7. **Natural coordination**: Workers share state via Redis (`recent_bot_posts`)

### Negative

1. **Secrets in Redis**: Acceptable for internal Docker network; may need encryption for external access
2. **Bot must be running**: If bot dies, secrets expire (24h TTL). Workers fail gracefully.
3. **Character config loading**: Workers need access to `characters/` directory (mount in Docker)

### Neutral

1. **Cron jobs**: Can use same pattern — look up secrets from vault
2. **Existing shared worker**: Can migrate incrementally; current arq worker still works

## Alternatives Considered

### Per-Bot Dedicated Workers

Each bot gets its own worker with token in env file.

**Rejected because:**
- More containers (N bots × 2)
- Duplicate configuration
- Less flexible scaling

### Token in Job Payload

Bot includes token in every event sent to inbox.

**Partially viable:**
- Works for bot-initiated tasks
- Doesn't work for cron jobs (no initiating event)
- Less secure (token in many places)

### HashiCorp Vault / AWS Secrets Manager

External secrets management service.

**Deferred:**
- Overkill for solo dev
- Redis vault has same interface, can migrate later

## Implementation Plan

### Phase 1: Secrets Vault

1. Add `SecretsVault` class to `src_v2/core/secrets.py`
2. Bot publishes secrets on startup (`publish_secrets()`)
3. Periodic refresh (every hour)

### Phase 2: Discord REST Client

1. Add `DiscordRESTClient` to `src_v2/discord/rest_client.py`
2. Methods: `send_message()`, `add_reaction()`, `fetch_messages()`
3. Takes token as parameter (from vault)

### Phase 3: Generic Worker

1. Modify worker to read from multiple inboxes
2. Look up secrets per job based on `bot_name`
3. Load character config dynamically

### Phase 4: Bot Inbox Publishing

1. Bot captures channel messages → `XADD inbox:{bot_name}`
2. Fire-and-forget (non-blocking)
3. Direct engagements still processed immediately

### Phase 5: Coordination Layer

1. `channel:{id}:recent_bot_posts` sorted set
2. Workers check before responding
3. Configurable cooldown (e.g., 30s)

## Related

- **ADR-013**: Event-Driven Architecture (this implements the "inbox" concept)
- **ADR-015**: Daily Life Unified Autonomy (superseded by this for autonomous features)
- **SPEC-E36**: "The Stream" (related Redis event patterns)
