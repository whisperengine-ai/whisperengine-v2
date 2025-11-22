## ✅ Phase 2: Long-Term Memory (Vector RAG) (Completed)
**Goal**: Give the bot "episodic memory" so it remembers details from past conversations.

- [x] **Embedding Service**: 
    - Implement `src_v2/memory/embeddings.py`.
    - Use `fastembed` to generate 384-dimension vectors locally (matching WE1).
    - **Async Support**: Implemented `embed_query_async` for non-blocking generation.
- [x] **Vector Storage**: 
    - Update `MemoryManager.add_message` to upsert vectors into Qdrant.
    - Store metadata: `user_id`, `role`, `content`, `timestamp`.
    - **Named Vectors**: Implemented `content`, `emotion`, `semantic` vectors.
- [x] **Semantic Retrieval**: 
    - Implement `MemoryManager.search_memories(query, user_id)`.
    - Filter by `user_id` to ensure privacy.
- [x] **Context Injection**: 
    - Update `src_v2/discord/bot.py` to fetch relevant memories.
    - Inject them into the `{recent_memories}` placeholder in the character prompt.

---
