# Document RAG (Retrieval-Augmented Generation)

**Status**: ✅ Implemented  
**Version**: 2.0  
**Last Updated**: November 26, 2025

## Overview

WhisperEngine v2 supports uploading documents (PDF, Word, Text files) that are:
1. **Processed immediately** for the current conversation
2. **Stored in vector memory** for future retrieval via semantic search
3. **Automatically trigger deeper analysis** via complexity classification

This allows users to share documents with the bot and refer back to them in later conversations.

## Supported File Types

| Type | Extensions | Loader |
|------|------------|--------|
| PDF | `.pdf` | PyPDFLoader |
| Word | `.docx`, `.doc` | Docx2txtLoader |
| Text | `.txt`, `.md`, `.json`, etc. | TextLoader |

**Note**: Images are handled separately via the Vision system and are NOT stored as text in RAG.

## How It Works

### 1. Upload Flow

```
User uploads file → Discord attachment detected
                         ↓
              _process_attachments()
                         ↓
              document_processor.process_attachment()
                         ↓
              Text extracted (up to 20KB per file)
                         ↓
              ┌─────────────────────────────────────────┐
              │                                         │
              ▼                                         ▼
    FULL content saved to              PREVIEW (2KB) sent to LLM
    Qdrant vector memory               for immediate response
              │                                         │
              └─────────────────────────────────────────┘
                         ↓
              Future: RAG retrieves full content via search
```

**Key Design**: We store the FULL document in Qdrant, but only send a 2KB preview to the LLM 
for immediate responses. This prevents context window overload while preserving all content 
for future retrieval.

### 2. Storage Format

When a document is uploaded, the message saved to memory looks like:

```
User's message text

[Attached File Content]:
--- File: quarterly_report.pdf ---
Revenue increased by 20% in Q3...
[Content continues...]
```

**Metadata stored**:
- `has_attachments`: `true`
- `filenames`: `["quarterly_report.pdf", "notes.txt"]` (extracted from headers)
- Standard fields: `user_id`, `timestamp`, `channel_id`, etc.

### 3. Retrieval

When the user asks about a document later:

```
User: "What was in that quarterly report?"
              ↓
      Semantic search in Qdrant
              ↓
      Finds memory with "quarterly report" content
              ↓
      Injects into context as [RELEVANT MEMORY]
              ↓
      Bot answers using retrieved content
```

**Search methods**:
- **Semantic**: "What was the revenue growth?" matches content about "20% increase"
- **Keyword**: "quarterly_report.pdf" matches filename in message text
- **Topic**: "financial documents" matches related concepts

### 4. Complexity Classification

Documents automatically trigger higher complexity tiers:

| Scenario | Complexity | Reason |
|----------|------------|--------|
| File attached, simple question | `COMPLEX_MID` | Analysis of attached content |
| File attached, "summarize this" | `COMPLEX_MID` | Summarization task |
| File attached, deep analysis | `COMPLEX_HIGH` | Multi-step reasoning |
| Just "here's a file" | `COMPLEX_LOW` | Simple acknowledgement |

This is configured in `src_v2/agents/classifier.py`:
```python
# If the input contains [Attached File Content], default to COMPLEX_MID
```

## File Size Limits

| Limit | Value | Reason |
|-------|-------|--------|
| Max file size | 25 MB | Discord attachment limit |
| Max files per message | 10 | Prevent spam/abuse |
| Text extraction limit | 20 KB | Context window management |
| Referenced file limit | 10 KB | Lower priority content |

Files exceeding these limits are:
- Silently skipped (with logging)
- User notified for oversized files

## Code Locations

| Component | File | Function |
|-----------|------|----------|
| Attachment processing | `src_v2/discord/bot.py` | `_process_attachments()` |
| Text extraction | `src_v2/knowledge/documents.py` | `DocumentProcessor` |
| Memory storage | `src_v2/discord/bot.py` | Line ~790 (save with file content) |
| Vector storage | `src_v2/memory/manager.py` | `add_message()` → `_save_vector_memory()` |
| Complexity classification | `src_v2/agents/classifier.py` | `classify()` |

## Example Interactions

### Immediate Analysis
```
User: [uploads report.pdf] Can you summarize this?
Bot: [COMPLEX_MID triggered]
     📄 Reading report.pdf...
     ✨ **Using my abilities...**
     > 🔍 Checking my memory...
     
     This quarterly report shows three key points:
     1. Revenue grew 20% YoY
     2. Customer acquisition cost decreased
     3. New product launch exceeded targets...
```

### Later Retrieval
```
User: What did that report say about customer costs?
Bot: [Searches vector memory]
     [Finds: "Customer acquisition cost decreased by 15%..."]
     
     The quarterly report mentioned that customer acquisition
     costs dropped by 15% compared to the previous quarter...
```

### Multiple Documents
```
User: [uploads doc1.pdf, doc2.txt] Compare these two documents
Bot: [COMPLEX_HIGH triggered - multi-document analysis]
     🧠 **Reflective Mode**
     > 💭 Analyzing both documents...
     > 🛠️ *Using search_memories...*
     > ✅ *search_memories*: Found document content...
     
     Comparing the two documents:
     - Document 1 focuses on...
     - Document 2 emphasizes...
     - Key differences include...
```

## Limitations

1. **No OCR**: Scanned PDFs without embedded text won't extract content
2. **No Tables**: Complex table formatting may be lost in extraction
3. **Truncation**: Very long documents are truncated to 20KB
4. **No Binary**: Images, videos, audio files are handled by Vision, not RAG
5. **Single User**: Documents are stored per-user, not shared across users

## Future Enhancements

- [ ] Chunked storage for very long documents (preserve full content)
- [ ] Explicit filename search filter in Qdrant
- [x] ~~Document summarization before storage (reduce token usage)~~ → Implemented as preview-only approach
- [ ] Cross-user document sharing (with permissions)
- [ ] OCR integration for scanned documents

## Related Features

- [Vision System](./VISION.md) - Image analysis
- [Memory System](../architecture/DATA_MODELS.md) - Vector storage
- [Reflective Mode](./REFLECTIVE_MODE_CONTROLS.md) - Deep analysis
