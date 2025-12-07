# REF-033: Vision Analysis Flow

**Version:** 1.0  
**Last Updated:** December 6, 2025  
**Status:** Current

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Documentation request |
| **Proposed by** | Mark + Claude (collaborative) |
| **Key insight** | Vision analysis has two parallel paths: inline for immediate response, async for memory storage |

---

## Overview

When a user uploads an image, WhisperEngine processes it through **two parallel flows**:

1. **Inline Vision** — Image URLs passed directly to the LLM for immediate response (sync)
2. **Background Vision Analysis** — Image analyzed and stored as visual memory for future recall (async)

This document traces the complete round-trip of the background vision analysis pipeline.

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TWO PARALLEL FLOWS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USER UPLOADS IMAGE                                                         │
│         │                                                                   │
│         ├──────────────────────────────────────┐                            │
│         │                                      │                            │
│         ▼                                      ▼                            │
│  ┌─────────────────────┐            ┌─────────────────────────┐             │
│  │  INLINE VISION      │            │  BACKGROUND ANALYSIS    │             │
│  │  (Sync)             │            │  (Async via arq)        │             │
│  │                     │            │                         │             │
│  │  image_urls passed  │            │  task_queue.enqueue_    │             │
│  │  to LLM for         │            │  vision_analysis()      │             │
│  │  immediate response │            │                         │             │
│  │                     │            │  Stores visual memory   │             │
│  │  User sees response │            │  for future recall      │             │
│  │  that "sees" image  │            │                         │             │
│  └─────────────────────┘            └─────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Round Trip Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER SENDS IMAGE IN DISCORD                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1️⃣ DISCORD MESSAGE HANDLER                                                 │
│  Location: src_v2/discord/handlers/message_handler.py                       │
│                                                                             │
│  on_message() receives message with attachment                              │
│      │                                                                      │
│      ▼                                                                      │
│  _process_attachments() (line 2046)                                         │
│      ├─ Check: is_image(attachment) → content_type.startswith("image/")     │
│      ├─ Add URL to image_urls list                                          │
│      └─ if trigger_vision and settings.LLM_SUPPORTS_VISION:                 │
│             await task_queue.enqueue_vision_analysis(...)  ──────┐          │
│                                                                  │          │
│  image_urls are also passed to generate_response_stream()        │          │
│  for inline LLM vision (immediate response)                      │          │
└──────────────────────────────────────────────────────────────────┼──────────┘
                                                                   │
                    ┌──────────────────────────────────────────────┘
                    │  ASYNC (Fire & Forget)
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2️⃣ TASK QUEUE - ENQUEUE                                                    │
│  Location: src_v2/workers/task_queue.py:317                                 │
│                                                                             │
│  async def enqueue_vision_analysis(image_url, user_id, channel_id):         │
│      return await self.enqueue(                                             │
│          "run_vision_analysis",                                             │
│          _queue_name=self.QUEUE_SENSORY,  # arq:sensory queue               │
│          image_url=image_url,                                               │
│          user_id=user_id,                                                   │
│          channel_id=channel_id                                              │
│      )                                                                      │
│                                                                             │
│  Job pushed to Redis → arq:sensory queue                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                           ┌────────────────┐
                           │   REDIS        │
                           │  arq:action    │
                           │    queue       │
                           └────────────────┘
                                    │
                                    │ (Picked up by worker)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3️⃣ ARQ WORKER                                                              │
│  Location: src_v2/workers/worker.py                                         │
│                                                                             │
│  WorkerSettings.functions = [                                               │
│      ...                                                                    │
│      run_vision_analysis,  # Registered task handler                        │
│      ...                                                                    │
│  ]                                                                          │
│                                                                             │
│  Worker polls Redis, picks up job, executes run_vision_analysis()           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4️⃣ VISION TASK                                                             │
│  Location: src_v2/workers/tasks/vision_tasks.py                             │
│                                                                             │
│  async def run_vision_analysis(ctx, image_url, user_id, channel_id):        │
│      if not settings.LLM_SUPPORTS_VISION:                                   │
│          return {"success": False, "reason": "vision_disabled"}             │
│                                                                             │
│      from src_v2.vision.manager import vision_manager                       │
│      await vision_manager.analyze_and_store(image_url, user_id, channel_id) │
│      return {"success": True, ...}                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5️⃣ VISION MANAGER - ANALYZE                                                │
│  Location: src_v2/vision/manager.py                                         │
│                                                                             │
│  async def analyze_and_store(image_url, user_id, channel_id):               │
│      │                                                                      │
│      ├─ 5a. Try URL-based analysis first                                    │
│      │      description = await self._try_analyze_image(image_url)          │
│      │                                                                      │
│      ├─ 5b. If fails, fallback to base64                                    │
│      │      b64_url = await self._fetch_image_as_base64(image_url)          │
│      │      description = await self._try_analyze_image(b64_url)            │
│      │                                                                      │
│      └─ 5c. _try_analyze_image() → LLM call                                 │
│             prompt = HumanMessage(content=[                                 │
│                 {"type": "text", "text": "Describe this image..."},         │
│                 {"type": "image_url", "image_url": {"url": image_url}}      │
│             ])                                                              │
│             response = await self.llm.ainvoke(prompt)                       │
│                 │                                                           │
│                 ▼                                                           │
│         ┌─────────────────────────────────────┐                             │
│         │  REFLECTIVE LLM                     │                             │
│         │  (e.g., Claude 3.5 Haiku)           │                             │
│         │                                     │                             │
│         │  Input: Image + "Describe this..."  │                             │
│         │  Output: "A sunset over the ocean   │                             │
│         │          with orange and purple..." │                             │
│         └─────────────────────────────────────┘                             │
│                                                                             │
│      description = "A sunset over the ocean with orange and purple skies"  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6️⃣ VISION MANAGER - STORE                                                  │
│  Location: src_v2/vision/manager.py:analyze_and_store()                     │
│                                                                             │
│  # Format as visual memory                                                  │
│  memory_content = f"[Visual Memory] User sent an image. Description: {description}"
│                                                                             │
│  # Store in Qdrant via memory_manager                                       │
│  await memory_manager.add_message(                                          │
│      user_id=user_id,                                                       │
│      character_name=settings.DISCORD_BOT_NAME,                              │
│      role="system",  # Stored as system observation, not user message       │
│      content=memory_content,                                                │
│      channel_id=channel_id,                                                 │
│      metadata={"type": "image_analysis", "image_url": image_url}            │
│  )                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7️⃣ MEMORY MANAGER - VECTOR STORAGE                                         │
│  Location: src_v2/memory/manager.py                                         │
│                                                                             │
│  add_message() →                                                            │
│      ├─ Generate embedding via EmbeddingService (384D)                      │
│      ├─ Store in Qdrant collection: whisperengine_memory_{bot_name}         │
│      │      Point(                                                          │
│      │          id=uuid,                                                    │
│      │          vector=[0.123, -0.456, ...],  # 384 dims                    │
│      │          payload={                                                   │
│      │              "content": "[Visual Memory] User sent an image...",     │
│      │              "user_id": "123456789",                                 │
│      │              "type": "image_analysis",                               │
│      │              "image_url": "https://cdn.discord...",                  │
│      │              "timestamp": "2025-12-06T10:30:00Z"                     │
│      │          }                                                           │
│      │      )                                                               │
│      └─ Also store in PostgreSQL chat_history table                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ✅ COMPLETE                                                                 │
│                                                                             │
│  The visual memory is now:                                                  │
│  • Searchable via semantic similarity (Qdrant vector search)                │
│  • Recallable in future conversations: "Remember that sunset I showed you?" │
│  • Tagged with metadata for filtering (type: image_analysis)                │
│                                                                             │
│  Total latency: ~2-5 seconds (LLM vision call dominates)                    │
│  User impact: None (async, user got response immediately)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Summary

| Stage | Component | Location | Blocking? | Purpose |
|-------|-----------|----------|-----------|---------|
| 1 | `_process_attachments` | `message_handler.py:2046` | No | Detect images, enqueue analysis |
| 2 | `enqueue_vision_analysis` | `task_queue.py:317` | No | Push to Redis queue |
| 3 | arq worker | `worker.py` | Async | Poll queue, execute tasks |
| 4 | `run_vision_analysis` | `vision_tasks.py` | Worker-side | Task wrapper |
| 5 | `analyze_and_store` | `vision/manager.py` | Worker-side | LLM vision call |
| 6 | Memory formatting | `vision/manager.py` | Worker-side | Create memory content |
| 7 | Vector storage | `memory/manager.py` | Worker-side | Persist for recall |

---

## Key Files

| File | Purpose |
|------|---------|
| `src_v2/discord/handlers/message_handler.py` | Entry point, attachment detection |
| `src_v2/workers/task_queue.py` | Task queue management, enqueue methods |
| `src_v2/workers/tasks/vision_tasks.py` | Vision task definition |
| `src_v2/workers/worker.py` | arq worker configuration |
| `src_v2/vision/manager.py` | Vision analysis and storage logic |
| `src_v2/memory/manager.py` | Vector memory storage |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_SUPPORTS_VISION` | `true` | Enable/disable vision pipeline |
| `QUEUE_SENSORY` | `arq:sensory` | Redis queue for vision tasks (sensory/perception) |

---

## Inline vs Background: Why Both?

### Inline Vision (Sync)
- **Purpose:** Let the LLM "see" the image to generate an appropriate response
- **Example:** User sends a meme → Bot laughs and comments on it
- **Blocking:** Yes, but necessary for coherent response

### Background Vision (Async)
- **Purpose:** Store a detailed description for future memory recall
- **Example:** "Remember that sunset photo I showed you last week?"
- **Blocking:** No, runs in background worker

Both are needed because:
1. The **inline** path uses the main LLM with context (chat history, system prompt) for response generation
2. The **background** path uses a dedicated vision prompt for detailed, objective description optimized for memory retrieval

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Vision disabled (`LLM_SUPPORTS_VISION=false`) | Task returns early, no analysis |
| Image URL inaccessible | Fallback to base64 download |
| Base64 fallback fails | Log error, return `None` |
| LLM call fails | Log error, memory not stored |
| Redis unavailable | Task not enqueued (logged as error) |

---

## Future Enhancements

See `docs/roadmaps/VISION_FACT_EXTRACTION.md` for planned feature:
- Extract structured facts from images to Neo4j knowledge graph
- Example: "User has a cat named Whiskers" extracted from pet photo

---

## Related Documents

- [REF-011: Vision Pipeline](./REF-011-VISION_PIPELINE.md) — Broader vision architecture
- [REF-007: Multi-Modal Perception](./REF-007-MULTI_MODAL_PERCEPTION.md) — How agents perceive
- [REF-022: Background Workers](./REF-022-BACKGROUND_WORKERS.md) — Task queue architecture
- [REF-003: Memory System](./REF-003-MEMORY_SYSTEM.md) — Vector memory storage
