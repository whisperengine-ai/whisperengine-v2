# WhisperEngine v2 API Reference

**Version**: 2.0.0  
**Base URL**: `http://localhost:{PORT}` (port varies per bot)

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
| `context` | object | ❌ | `null` | Additional context variables passed to the character's prompt template. |

**Example Request**:
```json
{
  "user_id": "user_12345",
  "message": "Hey! What's your favorite book?",
  "context": {
    "channel_name": "general",
    "guild_name": "My Server"
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

**Example Response**:
```json
{
  "success": true,
  "response": "Oh, I love discussing books! I've been really into sci-fi lately. Have you read any Isaac Asimov?",
  "timestamp": "2025-01-15T14:32:00.123456",
  "bot_name": "elena",
  "processing_time_ms": 1245.67,
  "memory_stored": true
}
```

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
