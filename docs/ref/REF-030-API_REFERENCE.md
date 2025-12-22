# WhisperEngine v2 API Reference

**Version**: 2.1.0  
**Last Updated**: December 3, 2025  
**Architecture**: E17 Supergraph (Primary), Legacy orchestration (Fallback)  
**Base URL**: `http://localhost:{PORT}` (port varies per bot)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | API documentation |
| **Proposed by** | Mark (developer reference) |
| **Key insight** | REST API for local integrations — testing, diagnostics, multi-turn conversations |

---

## Overview

WhisperEngine exposes a REST API for interacting with AI characters. Each bot instance runs on a unique port. This API is designed for **local integrations only** (localhost, Docker internal network).

### Bot Ports

| Bot | Port | Status |
|-----|------|--------|
| elena | 8000 | Production |
| ryan | 8001 | Test |
| dotty | 8002 | Production |
| aria | 8003 | Test |
| dream | 8004 | Test |
| jake | 8005 | Test |
| sophia | 8006 | Test |
| marcus | 8007 | Test |
| nottaylor | 8008 | Production |

---

## Endpoints

### POST `/api/chat`

Send a message to the character and receive a response.

#### Request

**Content-Type**: `application/json`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `user_id` | string | ✅ | - | Unique identifier for the user. Used for memory retrieval and relationship tracking. |
| `message` | string | ✅ | - | The user's message to the character. |
| `context` | object | ❌ | `null` | Additional context variables passed to the character's prompt template. See **Context Fields** below. |
| `force_mode` | string | ❌ | `null` | Override auto-detected complexity mode. See **Mode Override** below. |

##### Mode Override

The `force_mode` field allows you to bypass the automatic complexity classifier:

| Value | Description | Use Case |
|-------|-------------|----------|
| `null` (default) | Auto-detect complexity | Normal usage - let the system decide |
| `"fast"` | Single-pass LLM, no tools | Simple integrations, lower latency, cost savings |
| `"reflective"` | Full ReAct reasoning loop | Force deep thinking for complex queries |

**Example - Force Fast Mode** (single-pass LLM):
```json
{
  "user_id": "app_user_123",
  "message": "What's the weather like?",
  "force_mode": "fast"
}
```

This skips complexity classification and tool usage, returning a direct LLM response. Useful for:
- Applications that don't need memory/knowledge lookups
- Reducing latency and API costs
- Simple chatbot integrations

##### Context Fields

The `context` object supports these optional fields to simulate Discord environment:

| Field | Type | Description | Effect on Bot |
|-------|------|-------------|---------------|
| `user_name` | string | Display name of the user | Used in system prompt `{user_name}` template |
| `guild_id` | string | Discord server (guild) ID | Used by universe tools to look up server info |
| `channel_name` | string | Name of the current channel | Injected as `[CHANNEL CONTEXT]` in prompt |
| `parent_channel_name` | string | For threads, the parent channel name | Context for thread discussions |
| `is_thread` | boolean | Whether message is in a thread | Adjusts context building |
| `current_datetime` | string | ISO timestamp | Overrides auto-generated timestamp |

**For basic testing**, these are all optional - the bot will respond normally without them.

**When context matters**:
- **Memory is NOT segmented by channel/guild** - a user's memories are shared across all contexts
- **Channel name** appears in the bot's system prompt so it knows where it is
- **Guild ID** is used by `CheckPlanetContextTool` for universe lookups (if you have universe configurations)

**Minimal Example** (no context needed):
```json
{
  "user_id": "test_user_123",
  "message": "Hello, how are you?"
}
```

**Full Discord-like Example**:
```json
{
  "user_id": "user_12345",
  "message": "Hey! What's your favorite book?",
  "context": {
    "user_name": "MarkC",
    "guild_id": "123456789012345678",
    "channel_name": "general",
    "parent_channel_name": null,
    "is_thread": false
  }
}
```

#### Response

**Content-Type**: `application/json`

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the request was processed successfully. |
| `response` | string | The character's response message. |
| `timestamp` | datetime | ISO 8601 timestamp of the response. |
| `bot_name` | string | Name of the character that responded. |
| `processing_time_ms` | float | Time taken to generate the response in milliseconds. |
| `memory_stored` | boolean | Whether the interaction was stored in memory. |
| `mode` | string \| null | Processing mode: `"supergraph"` (primary), `"fast"`, `"agency"`, `"reflective"` (legacy fallback), or `"blocked"`. |
| `complexity` | string \| null | Complexity tier: `"SIMPLE"`, `"COMPLEX_LOW"`, `"COMPLEX_MID"`, `"COMPLEX_HIGH"`, `"DYNAMIC"` (Supergraph), or `"MANIPULATION"`. |
| `model_used` | string \| null | LLM model that generated the response (e.g., `"openai/gpt-4o"`, `"mixed"` for Supergraph). |

**Example Response**:
```json
{
  "success": true,
  "response": "Oh, I love discussing books! I've been really into sci-fi lately. Have you read any Isaac Asimov?",
  "timestamp": "2025-01-15T14:32:00.123456",
  "bot_name": "elena",
  "processing_time_ms": 1245.67,
  "memory_stored": true,
  "mode": "supergraph",
  "complexity": "DYNAMIC",
  "model_used": "mixed"
}
```

**Mode Values** (E17 - December 2025):
| Mode | Description |
|------|-------------|
| `supergraph` | **Primary path**: LangGraph orchestration with context retrieval, classification, and routing (all user_id requests) |
| `fast` | Legacy: Direct LLM call without tool usage (fallback for API calls without user_id) |
| `agency` | Legacy: Single tool call (fallback for Tier 2 - memory lookup) |
| `reflective` | Legacy: Full ReAct reasoning loop with multiple tool calls (fallback) |
| `blocked` | Manipulation attempt rejected |

**Note**: As of E17 (December 2025), all Discord messages and API calls with `user_id` use the Supergraph orchestration path. Legacy modes are only used for stateless API calls without user context.

**Complexity Values**:
| Complexity | Triggers |
|------------|----------|
| `SIMPLE` | Greetings, casual chat → Fast mode |
| `COMPLEX_LOW` | Questions needing single lookup → Agency mode |
| `COMPLEX_MID` | Multi-step reasoning → Reflective mode (10 steps) |
| `COMPLEX_HIGH` | Complex analysis → Reflective mode (15 steps) |
| `MANIPULATION` | Jailbreak attempts → Blocked |

#### Error Responses

| Status | Description |
|--------|-------------|
| `400` | Invalid request body |
| `500` | Server error (bot not configured, character not found, LLM error) |

**Error Response Format**:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

### GET `/health`

Check if the bot API is healthy and responding.

#### Request

No parameters required.

#### Response

**Content-Type**: `application/json`

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Health status (`"healthy"`). |
| `timestamp` | datetime | ISO 8601 timestamp of the health check. |

**Example Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T14:35:00.000000"
}
```

---

## Diagnostic Endpoints

These endpoints are designed for testing, debugging, and regression testing.

### GET `/api/diagnostics`

Get bot configuration, database status, and feature flags.

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `bot_name` | string | Character name |
| `llm_models` | object | LLM models configured (main, reflective, router) |
| `database_status` | object | Connection status for each database |
| `feature_flags` | object | Enabled feature flags |
| `queue_depths` | object | Number of pending jobs in each worker queue |
| `uptime_seconds` | float | Seconds since bot started |
| `version` | string | Bot version |

**Example Response**:
```json
{
  "bot_name": "elena",
  "llm_models": {
    "main": "openai/gpt-4o",
    "reflective": "openai/gpt-4o",
    "router": "openai/gpt-4o-mini"
  },
  "database_status": {
    "postgres": true,
    "qdrant": true,
    "neo4j": true,
    "redis": true
  },
  "feature_flags": {
    "reflective_mode": false,
    "fact_extraction": true,
    "preference_extraction": true,
    "proactive_messaging": false
  },
  "queue_depths": {
    "cognition": 0,
    "sensory": 2,
    "action": 0,
    "social": 0
  },
  "uptime_seconds": 3600.5,
  "version": "2.0.0"
}
```

---

### POST `/api/user-state`

Get user state including trust level, memories, and knowledge facts.

#### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | ✅ | User ID to look up |

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string | User ID |
| `trust_score` | int | Current trust score |
| `trust_level` | string | Trust level label (Stranger, Acquaintance, etc.) |
| `memory_count` | int | Number of stored memories |
| `recent_memories` | array | Last 5 memories |
| `knowledge_facts` | array | Known facts about this user |

**Example Response**:
```json
{
  "user_id": "user_12345",
  "trust_score": 15,
  "trust_level": "Acquaintance",
  "memory_count": 5,
  "recent_memories": [
    {"content": "User mentioned they like coffee", "score": 0.85}
  ],
  "knowledge_facts": [
    {"fact": "User likes coffee"}
  ]
}
```

---

### POST `/api/conversation`

Run a multi-turn conversation test.

#### Request

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `user_id` | string | ✅ | - | User ID for the conversation |
| `messages` | array | ✅ | - | List of messages to send in sequence |
| `context` | object | ❌ | null | Shared context for all messages |
| `delay_between_ms` | int | ❌ | 500 | Delay between messages in milliseconds |

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether all turns succeeded |
| `user_id` | string | User ID |
| `bot_name` | string | Character name |
| `turns` | array | Array of conversation turns |
| `total_time_ms` | float | Total conversation time |

**Example Response**:
```json
{
  "success": true,
  "user_id": "test_user",
  "bot_name": "elena",
  "turns": [
    {
      "user_message": "Hi!",
      "bot_response": "Hello! How are you?",
      "processing_time_ms": 1200,
      "mode": "fast",
      "complexity": "SIMPLE"
    },
    {
      "user_message": "What's your name?",
      "bot_response": "I'm Elena! Nice to meet you.",
      "processing_time_ms": 1100,
      "mode": "fast",
      "complexity": "SIMPLE"
    }
  ],
  "total_time_ms": 2800
}
```

---

### POST `/api/clear-user-data`

Clear user data for test isolation. Use for test setup/teardown.

#### Request

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `user_id` | string | ✅ | - | User ID to clear |
| `clear_memories` | boolean | ❌ | true | Clear vector memories |
| `clear_trust` | boolean | ❌ | true | Reset trust score |
| `clear_knowledge` | boolean | ❌ | false | Clear knowledge graph facts |

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether operation succeeded |
| `user_id` | string | User ID |
| `memories_cleared` | int | Number of memories cleared |
| `trust_reset` | boolean | Whether trust was reset |
| `knowledge_cleared` | int | Number of knowledge facts cleared |

**Example Response**:
```json
{
  "success": true,
  "user_id": "test_user",
  "memories_cleared": 1,
  "trust_reset": true,
  "knowledge_cleared": 0
}

---

### POST `/api/user-graph`

Get user's knowledge graph subgraph for visualization (D3.js compatible).

#### Request

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `user_id` | string | ✅ | - | User ID to get graph for |
| `depth` | int | ❌ | 2 | Max depth to traverse from user node (1-4) |
| `include_other_users` | boolean | ❌ | false | Include other users connected through shared entities |
| `max_nodes` | int | ❌ | 50 | Maximum nodes to return (10-100) |

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether operation succeeded |
| `user_id` | string | User ID |
| `bot_name` | string | Character name |
| `nodes` | array | List of graph nodes |
| `edges` | array | List of graph edges |
| `clusters` | array | Thematic clusters of nodes |
| `stats` | object | Graph statistics (node_count, edge_count, etc.) |

**Example Response**:
```json
{
  "success": true,
  "user_id": "user_12345",
  "bot_name": "elena",
  "nodes": [
    {
      "id": "user_12345",
      "label": "User",
      "name": "MarkC",
      "score": 1.0,
      "properties": {}
    },
    {
      "id": "entity_coffee",
      "label": "Entity",
      "name": "Coffee",
      "score": 0.8,
      "properties": {"category": "beverage"}
    }
  ],
  "edges": [
    {
      "source": "user_12345",
      "target": "entity_coffee",
      "edge_type": "LIKES",
      "properties": {"weight": 0.9}
    }
  ],
  "clusters": [
    {
      "theme": "Preferences",
      "node_ids": ["user_12345", "entity_coffee"],
      "cohesion_score": 0.85
    }
  ],
  "stats": {
    "node_count": 2,
    "edge_count": 1,
    "cluster_count": 1,
    "max_depth": 2,
    "processing_time_ms": 250.5
  }
}
```

---

## Usage Examples

### cURL

```bash
# Health check
curl http://localhost:8000/health

# Send a chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_12345",
    "message": "Hello! How are you today?"
  }'

# Get diagnostics
curl http://localhost:8000/api/diagnostics

# Get user state
curl -X POST http://localhost:8000/api/user-state \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_12345"}'

# Get user graph
curl -X POST http://localhost:8000/api/user-graph \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_12345",
    "depth": 2
  }'

# Multi-turn conversation test
curl -X POST http://localhost:8000/api/conversation \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "messages": ["Hi!", "What is your name?", "Nice to meet you!"],
    "delay_between_ms": 500
  }'
```

### Python (httpx)

```python
import httpx
import asyncio

async def chat_with_bot():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/chat",
            json={
                "user_id": "user_12345",
                "message": "Hello! How are you today?"
            },
            timeout=60.0
        )
        data = response.json()
        print(f"Bot: {data['response']}")
        print(f"Processing time: {data['processing_time_ms']:.0f}ms")

asyncio.run(chat_with_bot())
```

### JavaScript (fetch)

```javascript
async function chatWithBot() {
  const response = await fetch('http://localhost:8000/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_id: 'user_12345',
      message: 'Hello! How are you today?',
    }),
  });
  
  const data = await response.json();
  console.log(`Bot: ${data.response}`);
  console.log(`Processing time: ${data.processing_time_ms.toFixed(0)}ms`);
}

chatWithBot();
```

---

## OpenAPI / Swagger

The API automatically generates OpenAPI documentation. Access it at:

- **Swagger UI**: `http://localhost:{PORT}/docs`
- **ReDoc**: `http://localhost:{PORT}/redoc`
- **OpenAPI JSON**: `http://localhost:{PORT}/openapi.json`

---

## Design Notes

### Local-Only API

This API is designed for local integrations:
- Development testing via localhost
- Docker internal network communication
- Same-machine service integrations

CORS is configured to allow all origins for ease of local development. No authentication is required since the API is not exposed to the public internet.

### Rate Limits & Timeouts

| Setting | Value | Notes |
|---------|-------|-------|
| Request Timeout | 60s recommended | Complex reflective queries may take 10-30s |
| Rate Limit | None | No rate limiting implemented |
| Max Message Length | No limit | LLM context window is the practical limit |

---

## Changelog

### v2.0.0 (Current)
- Initial API release
- POST `/api/chat` endpoint
- GET `/health` endpoint
- FastAPI with automatic OpenAPI generation
