# Document RAG (Retrieval-Augmented Generation)

**Status**: ✅ Implemented  
**Version**: 2.2  
**Last Updated**: December 1, 2025

## Overview

WhisperEngine v2 supports uploading documents (PDF, Word, Text files) that are:
1. **Processed immediately** for the current conversation (preview sent to LLM)
2. **Stored in full in vector memory** for future retrieval via semantic search
3. **Automatically trigger deeper analysis** via complexity classification (COMPLEX_MID or higher)

This allows users to share documents with the bot and refer back to them in later conversations.

## Supported File Types

| Type | Extensions | Loader |
|------|------------|--------|
| PDF | `.pdf` | `PyPDFLoader` (LangChain) |
| Word | `.docx`, `.doc` | `Docx2txtLoader` (LangChain) |
| Text | `.txt`, `.md`, `.json`, etc. | `TextLoader` (LangChain) |

**Note**: Images are handled separately via the Vision system and are NOT stored as text in RAG. Binary files (audio, video, executables) are skipped.

## Architecture

### Key Components

| Component | File | Purpose |
|-----------|------|---------||
| `DocumentProcessor` | `src_v2/knowledge/documents.py` | Downloads & extracts text from attachments |
| `DocumentContext` | `src_v2/knowledge/document_context.py` | Clean abstraction for document handling |
| `_process_attachments()` | `src_v2/discord/handlers/message_handler.py` | Routes images vs documents, enforces limits |
| `add_message()` | `src_v2/memory/manager.py` | Stores full content to Qdrant with metadata |
| `ComplexityClassifier` | `src_v2/agents/classifier.py` | Boosts complexity when documents present |

### Data Flow

```
User uploads file → Discord attachment detected
                         ↓
              _process_attachments()
                ├── Images → image_urls list (+ Vision analysis)
                └── Documents → document_processor.process_attachment()
                                        ↓
                              Text extracted (no size limit on extraction)
                                        ↓
                              DocumentContext.from_processed_files()
                                        ↓
              ┌─────────────────────────────────────────┐
              │                                         │
              ▼                                         ▼
    FULL content stored to             PREVIEW (2KB) sent to LLM
    Qdrant vector memory               for immediate response
    with metadata:                     with hint about full content
    - has_attachments: true            in memory
    - filenames: [...]
              │                                         │
              └─────────────────────────────────────────┘
                         ↓
              Future: RAG retrieves full content via semantic search
```

**Key Design**: We store the FULL document in Qdrant, but only send a 2,000 character preview to the LLM for immediate responses. This prevents context window overload while preserving all content for future retrieval.

## Storage Format

When a document is uploaded, the message saved to memory looks like:

```
User's message text

[Attached File Content]:
--- File: quarterly_report.pdf ---
Revenue increased by 20% in Q3...
[Full content stored here - no truncation]
```

**Metadata stored in Qdrant payload**:
```python
{
    "user_id": "123456789",
    "role": "human",
    "content": "...",  # Full message + document content
    "timestamp": "2025-11-27T10:30:00",
    "channel_id": "...",
    "message_id": "...",
    "has_attachments": True,
    "filenames": ["quarterly_report.pdf", "notes.txt"]
}
```

For referenced files (from replied-to messages), the prefix is `Referenced File` instead of `File`.

## LLM Context Format

When documents are present, the LLM receives a preview with a hint:

```
[Attached Files: quarterly_report.pdf, notes.txt]
--- File: quarterly_report.pdf ---
Revenue increased by 20% in Q3...
...[Content continues - 15000 more chars stored in memory]...

(Full document content has been stored in memory. 
Use search_specific_memories tool to find more details if needed.)
```

This encourages the LLM to use memory search for detailed queries rather than relying solely on the preview.

## Retrieval

When the user asks about a document later:

```
User: "What was in that quarterly report?"
              ↓
      Complexity classifier detects document follow-up
      (history_has_document_context check)
              ↓
      Routes to COMPLEX_LOW/MID (enables tool use)
              ↓
      LLM uses search_specific_memories tool
              ↓
      Semantic search in Qdrant finds memory with document content
              ↓
      Full content returned to LLM
              ↓
      Bot answers using retrieved content
```

**Search methods**:
- **Semantic**: "What was the revenue growth?" matches content about "20% increase"
- **Filename**: Filenames are stored in content text, so "quarterly_report.pdf" is searchable
- **Topic**: "financial documents" matches related concepts via embedding similarity

## Complexity Classification

Documents automatically trigger higher complexity tiers via `ComplexityClassifier`:

| Scenario | Complexity | Reason |
|----------|------------|--------|
| File attached + analysis question | `COMPLEX_MID` | Analysis of attached content |
| File attached + "summarize this" | `COMPLEX_MID` | Summarization task |
| File attached + deep analysis | `COMPLEX_HIGH` | Multi-step reasoning |
| Just "here's a file" (no question) | `SIMPLE` | Simple acknowledgement |
| Follow-up question after document | `COMPLEX_LOW+` | `history_has_document_context` detected |

**Classification rules** (from `classifier.py`):
```python
# If the input contains [Attached File Content] or [Attached Files:], 
# default to COMPLEX_MID unless the user just wants a simple acknowledgement.

# If recent history mentions documents, files, or images, and the user 
# asks a SHORT follow-up question, classify as COMPLEX_LOW or COMPLEX_MID.
```

## File Size Limits

| Limit | Value | Location | Reason |
|-------|-------|----------|--------|
| Max file size | 25 MB | `MessageHandler._process_attachments()` | Discord attachment limit |
| Max files per message | 10 | `MessageHandler._process_attachments()` | Prevent spam/abuse |
| LLM preview limit | 2,000 chars | `DocumentContext.PREVIEW_LIMIT` | Context window management |
| Text extraction | **No limit** | `DocumentProcessor` | Full content stored for RAG |

**Note**: Full document content is stored in Qdrant for better retrieval. Only the LLM preview is truncated to 2,000 characters.

**User Notifications**: When limits are exceeded, the user is notified upfront:
- **Too many files (>10)**: `⚠️ Too many files! I can only process the first 10 attachments.`
- **Oversized files (>25MB)**: `⚠️ Skipping oversized files (> 25MB): filename.pdf`

**File Processing**:
- **Images**: Added to `image_urls` list, optionally triggers Vision analysis
- **Documents**: Processed by `DocumentProcessor`, text extracted via LangChain loaders
- **Binary files**: Silently skipped (handled by Vision if image)

## Code Locations

| Component | File | Function/Class |
|-----------|------|----------------|
| Document processor | `src_v2/knowledge/documents.py` | `DocumentProcessor` class |
| Document context | `src_v2/knowledge/document_context.py` | `DocumentContext` dataclass |
| Attachment routing | `src_v2/discord/handlers/message_handler.py` | `MessageHandler._process_attachments()` |
| Memory storage | `src_v2/discord/handlers/message_handler.py` | `doc_context.format_for_memory()` |
| Vector storage | `src_v2/memory/manager.py` | `add_message()` → `_save_vector_memory()` |
| Complexity boost | `src_v2/agents/classifier.py` | `classify()` + `history_has_document_context()` |
| Context detection | `src_v2/knowledge/document_context.py` | `has_document_context()`, `history_has_document_context()` |

## Example Interactions

### Immediate Analysis
```
User: [uploads report.pdf] Can you summarize this?

Bot: 📄 Reading report.pdf...
     
     [COMPLEX_MID triggered - document analysis]
     [LLM receives preview with hint about full content in memory]
     
     This quarterly report shows three key points:
     1. Revenue grew 20% YoY
     2. Customer acquisition cost decreased
     3. New product launch exceeded targets...
```

### Later Retrieval
```
User: What did that report say about customer costs?

Bot: [history_has_document_context = True]
     [COMPLEX_LOW triggered - enables CharacterAgent with tools]
     
     [CharacterAgent uses search_specific_memories tool]
     [Finds: "Customer acquisition cost decreased by 15%..."]
     
     The quarterly report mentioned that customer acquisition
     costs dropped by 15% compared to the previous quarter...
```

### Multiple Documents
```
User: [uploads doc1.pdf, doc2.txt] Compare these two documents

Bot: 📄 Reading doc1.pdf...
     📄 Reading doc2.txt...
     
     [COMPLEX_MID/HIGH triggered - multi-document analysis]
     [ReflectiveAgent: ReAct loop with up to 10-15 steps]
     
     > 💭 Analyzing both documents...
     > 🛠️ Using search_specific_memories...
     > ✅ Found document content...
     
     Comparing the two documents:
     - Document 1 focuses on...
     - Document 2 emphasizes...
     - Key differences include...
```

### Referenced Documents (Reply Context)
```
User: [replies to message with attachment] What about this file?

Bot: [Silent processing of referenced attachment]
     [Full content from referenced file added to context]
     
     Based on the referenced file, I can see...
```

## Limitations

1. **No OCR**: Scanned PDFs without embedded text won't extract content
2. **No Tables**: Complex table formatting may be lost in extraction (flattened to text)
3. **No Binary Files**: Audio, video, executables are skipped (images go to Vision)
4. **Single User Scope**: Documents are stored per-user, not shared across users
5. **Embedding Context Limit**: Long documents may exceed embedding model's token limit (256 tokens for all-MiniLM-L6-v2), affecting semantic search quality for very long content
6. **No Explicit Filename Filter**: Currently relies on filename being in content text, not a dedicated Qdrant filter

## Known Gaps (Future Enhancements)

| Gap | Priority | Notes |
|-----|----------|-------|
| Chunked storage for long documents | Medium | Split into overlapping chunks with document_id linking |
| Explicit filename metadata filter | Low | Add Qdrant filter on `filenames` array for exact match |
| OCR for scanned PDFs | Low | Integrate Tesseract or cloud OCR API |
| Cross-user document sharing | Low | Would require permission system |
| Document expiration/cleanup | Low | Auto-delete old document memories |

**Completed enhancements**:
- ✅ ~~Document summarization before storage~~ → Replaced with preview-only approach (full content stored)
- ✅ ~~Text extraction limit~~ → Removed limit, store full content

## Related Features

- [Vision System](./VISION.md) - Image analysis (separate from document RAG)
- [Memory System](../architecture/DATA_MODELS.md) - Vector storage architecture
- [Cognitive Engine](../architecture/COGNITIVE_ENGINE.md) - Three-tier processing (Fast/Agency/Reflective)
- [Reflective Mode](./REFLECTIVE_MODE_CONTROLS.md) - Deep analysis mode triggered by documents

## Configuration

No specific settings for Document RAG. Related settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_RUNTIME_FACT_EXTRACTION` | `true` | Extract facts from documents to Neo4j |
| `LLM_SUPPORTS_VISION` | varies | Whether to trigger Vision for images |

## Implementation Notes

### DocumentProcessor Class

The `DocumentProcessor` handles file download and text extraction:

```python
class DocumentProcessor:
    def __init__(self, temp_dir: str = "temp_downloads"):
        # Creates temp directory for downloads
        
    async def process_attachment(self, attachment_url: str, filename: str) -> str:
        # Downloads file, extracts text, cleans up temp file
        
    async def process_local_file(self, file_path: Path) -> str:
        # Uses LangChain loaders based on file extension:
        # - .pdf → PyPDFLoader
        # - .docx/.doc → Docx2txtLoader  
        # - Other → TextLoader (for .txt, .md, .json, etc.)
```

### DocumentContext Class

The `DocumentContext` dataclass provides a clean abstraction:

```python
@dataclass
class DocumentContext:
    filenames: List[str]          # Extracted from headers
    full_content: str             # Complete document text
    preview_content: str          # First 2000 chars for LLM
    has_documents: bool           # Quick check flag
    
    PREVIEW_LIMIT: int = 2000     # Configurable preview size
    
    @classmethod
    def from_processed_files(cls, processed_files: List[str]) -> "DocumentContext":
        # Parses "--- File: name.pdf ---\nContent..." format
        # Extracts filenames via regex
        # Creates preview with "...[Content continues - X more chars]..." suffix
        
    def format_for_llm(self) -> str:
        # Returns preview with memory hint for tool usage
        
    def format_for_memory(self, user_message: str) -> str:
        # Returns message + full content for storage
        
    def get_memory_metadata(self) -> dict:
        # Returns {"has_attachments": True, "filenames": [...]}
```

### History Detection

Two utility functions check for document context:

```python
def has_document_context(message_content: str) -> bool:
    """Checks single message for document markers."""
    markers = [
        "[Attached Files:",
        "[Attached File Content]:",
        "[Visual Memory]"
    ]
    return any(marker in message_content for marker in markers)

def history_has_document_context(chat_history: list) -> bool:
    """Checks recent history for any document context."""
    for msg in chat_history:
        if hasattr(msg, 'content') and isinstance(msg.content, str):
            if has_document_context(msg.content):
                return True
    return False
```

These are used by the `ComplexityClassifier` to boost complexity for document follow-up questions. When `history_has_document_context` returns `True`, short follow-up questions like "search for X" or "what about Y" are classified as `COMPLEX_LOW` or higher to enable tool usage.

### Attachment Processing Flow

The `MessageHandler._process_attachments()` method handles all attachments:

1. **Limit Checks**: Max 10 files, max 25MB each
2. **User Notification**: Warns upfront about skipped files
3. **Image Handling**: Adds URL to `image_urls`, optionally triggers Vision analysis
4. **Document Handling**: Sends "📄 Reading filename..." message, extracts text
5. **Prefix Assignment**: `File:` for current message, `Referenced File:` for replies/forwards

```python
async def _process_attachments(
    self,
    attachments: List[discord.Attachment],
    channel: Any,
    user_id: str,
    silent: bool = False,        # True for referenced/forwarded messages
    trigger_vision: bool = False  # Whether to queue Vision analysis
) -> Tuple[List[str], List[str]]:  # (image_urls, processed_texts)
```
