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

Bots publish their secrets AND config to Redis on startup:

```python
# Bot process (on startup + periodic refresh)
await redis.hset(f"vault:{bot_name}:secrets", mapping={
    "discord_token": token,
    "openai_api_key": settings.OPENAI_API_KEY,
    "anthropic_api_key": settings.ANTHROPIC_API_KEY,
})

await redis.hset(f"vault:{bot_name}:llm", mapping={
    "main_model": settings.MAIN_MODEL,           # e.g., "claude-sonnet-4-20250514"
    "main_temperature": str(settings.MAIN_TEMPERATURE),  # e.g., "0.8"
    "reflective_model": settings.REFLECTIVE_MODEL,
    "reflective_temperature": str(settings.REFLECTIVE_TEMPERATURE),
    "router_model": settings.ROUTER_MODEL,
    "embedding_model": settings.EMBEDDING_MODEL,
})

await redis.hset(f"vault:{bot_name}:discord", mapping={
    "bot_user_id": str(bot.user.id),
    "guild_ids": json.dumps([g.id for g in bot.guilds]),
})

await redis.expire(f"vault:{bot_name}:secrets", 86400)
await redis.expire(f"vault:{bot_name}:llm", 86400)
await redis.expire(f"vault:{bot_name}:discord", 86400)
```

Workers read config on demand:

```python
class ConfigVault:
    async def get_secret(self, bot_name: str, key: str) -> str:
        return await redis.hget(f"vault:{bot_name}:secrets", key)
    
    async def get_llm_config(self, bot_name: str) -> dict:
        return await redis.hgetall(f"vault:{bot_name}:llm")
    
    async def get_discord_config(self, bot_name: str) -> dict:
        return await redis.hgetall(f"vault:{bot_name}:discord")

# Usage
vault = ConfigVault()
token = await vault.get_secret("elena", "discord_token")
llm_config = await vault.get_llm_config("elena")
# llm_config = {"main_model": "claude-sonnet-4-20250514", "main_temperature": "0.8", ...}
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
│   vault:elena:secrets  {discord_token, openai_key, ...}             │
│   vault:elena:llm      {main_model, main_temperature, ...}          │
│   vault:elena:discord  {bot_user_id, guild_ids}                     │
│   vault:dotty:secrets  {...}                                        │
│   vault:dotty:llm      {...}                                        │
│   inbox:elena          [event1, event2, ...]                        │
│   inbox:dotty          [event1, event2, ...]                        │
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
│    3. Fetch config: vault.get_llm_config(bot_name)                  │
│    4. Fetch secrets: vault.get_secret(bot_name, "discord_token")    │
│    5. Load character config for bot_name                             │
│    6. Should I respond? (LLM / heuristics)                          │
│    7. Check coordination: channel:{id}:recent_bot_posts             │
│    8. If yes: Generate response (LLM with bot's model + params)     │
│    9. Send via Discord REST API (with bot's token)                  │
│   10. Record: ZADD channel:{id}:recent_bot_posts bot_name {ts}      │
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

### 6. HTTP API (Enqueue + Poll)

The HTTP API (`/api/chat`) remains synchronous from the client's perspective, but delegates to workers:

```python
# Bot HTTP handler (thin)
@app.post("/api/chat")
async def chat(request: ChatRequest):
    job_id = str(uuid.uuid4())
    
    # Enqueue to worker (non-blocking, ~1ms)
    await redis.xadd(f"inbox:{bot_name}", {
        "job_id": job_id,
        "type": "http_chat",
        "user_id": request.user_id,
        "message": request.message,
    })
    
    # Poll for response (worker writes to response:{job_id})
    for _ in range(300):  # 30 second timeout
        response = await redis.get(f"response:{job_id}")
        if response:
            await redis.delete(f"response:{job_id}")  # cleanup
            return json.loads(response)
        await asyncio.sleep(0.1)
    
    raise HTTPException(504, "Timeout waiting for response")

# Worker writes response when done
async def process_http_chat(job: dict):
    job_id = job["job_id"]
    # ... do all the heavy work ...
    response = await generate_response(...)
    
    # Write response for bot to pick up
    await redis.setex(
        f"response:{job_id}",
        60,  # 60s TTL (cleanup if bot never reads)
        json.dumps({"response": response, "metadata": {...}})
    )
```

**Why this approach:**
- Same API contract — clients don't change
- Bot stays thin (enqueue ~1ms, poll ~100ms overhead)
- Worker does all heavy lifting
- Backward compatible with existing tests and integrations

## Consequences

### Positive

1. **Workers are generic**: Scale horizontally without per-bot configuration
2. **Single source of truth**: Secrets only in `.env.{bot}`, published to Redis
3. **No env files for workers**: Workers only need `REDIS_URL`
4. **Dynamic credential rotation**: Change token, restart bot, workers auto-update
5. **Solves gateway constraint**: Workers use REST, no conflict with bot's gateway
6. **Enables autonomous features**: Workers can now send to Discord directly
7. **Natural coordination**: Workers share state via Redis (`recent_bot_posts`)8. **Bot becomes ultra-thin**: No LLM calls, no embeddings, no DB queries — just event capture
9. **Bot never blocks**: `XADD` to Redis is ~1ms, bot stays responsive to Discord
10. **Horizontal scaling**: Add workers for compute, bot stays lightweight

### Bot Process Comparison

| Operation | Before (Coupled) | After (Vault) |
|-----------|------------------|---------------|
| Receive message | ✅ Bot | ✅ Bot |
| Generate embedding | ❌ Bot (100-500ms) | ✅ Worker |
| Query memories | ❌ Bot (50-200ms) | ✅ Worker |
| Query knowledge graph | ❌ Bot (50-200ms) | ✅ Worker |
| LLM call | ❌ Bot (1-10s) | ✅ Worker |
| Store memory | ❌ Bot | ✅ Worker |
| Send response | ❌ Bot | ✅ Worker (REST) |
| **Total blocking time** | **1.5-11s** | **~1ms** |

The bot process becomes a pure event gateway — receives from Discord, publishes to Redis, done. All compute-heavy work moves to workers which can scale independently.

### Scalability Implications

```
Before: 10 concurrent users → bot blocks on LLM → Discord rate limits → dropped messages

After:  10 concurrent users → bot queues 10 events in ~10ms
        Workers process in parallel → responses flow back via REST
        Bot never blocks, never hits Discord gateway limits
```
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

### Phase 1: Config Vault

1. Add `ConfigVault` class to `src_v2/core/vault.py`
2. Namespaced keys: `vault:{bot}:secrets`, `vault:{bot}:llm`, `vault:{bot}:discord`
3. Bot publishes all config on startup (`publish_vault()`)
4. Periodic refresh (every hour)

### Phase 2: Discord REST Client

1. Add `DiscordRESTClient` to `src_v2/discord/rest_client.py`
2. Methods: `send_message()`, `add_reaction()`, `fetch_messages()`
3. Takes token as parameter (from vault)

### Phase 3: Generic Worker

1. Modify worker to read from multiple inboxes
2. Look up config + secrets per job based on `bot_name`
3. Instantiate LLM client with bot's model/temperature settings
4. Load character config dynamically

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
