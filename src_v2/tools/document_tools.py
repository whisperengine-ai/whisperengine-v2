
from typing import Type, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger
from qdrant_client.models import Filter, FieldCondition, MatchValue

from src_v2.memory.manager import memory_manager
from src_v2.core.database import db_manager

class ReadDocumentInput(BaseModel):
    filename: str = Field(description="The exact filename of the document to read, including the extension (e.g., 'AUTONOMOUS_AGENTS_PHASE_3.md', 'design_doc.pdf').")

class ReadDocumentTool(BaseTool):
    name: str = "read_document"
    description: str = """Reads the full content of an attached document that was stored in memory. 

Use this tool when:
- The user uploads a file and asks about it ("what do you think of this?", "check this out", "read this")
- You see [Attached Files: filename] in the conversation
- The user asks to analyze, summarize, or evaluate a document

The filename must include the extension (e.g., 'AUTONOMOUS_AGENTS_PHASE_3.md')."""
    args_schema: Type[BaseModel] = ReadDocumentInput
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)

    def _run(self, filename: str) -> str:
        raise NotImplementedError("Use _arun instead")

    def _extract_document_content(self, content: str, filename: str) -> Optional[str]:
        """Extract document content from a memory that contains file markers."""
        # Try both marker formats
        marker = f"--- File: {filename} ---"
        if marker not in content:
            marker = f"--- Referenced File: {filename} ---"
        
        if marker not in content:
            return None
            
        # Split and get content after marker
        parts = content.split(marker, 1)
        if len(parts) <= 1:
            return None
            
        file_content = parts[1].strip()
        
        # Remove any subsequent file markers (if multiple files)
        if "--- File:" in file_content:
            file_content = file_content.split("--- File:")[0].strip()
        if "--- Referenced File:" in file_content:
            file_content = file_content.split("--- Referenced File:")[0].strip()
        
        # Remove trailing metadata if present
        if "[Attached File Content]:" in file_content:
            file_content = file_content.split("[Attached File Content]:")[0].strip()
            
        return file_content if file_content else None

    async def _reconstruct_from_chunks(self, parent_message_id: str, collection: str) -> Optional[str]:
        """
        Reconstruct a full document from its chunked memories.
        
        When documents exceed CHUNK_THRESHOLD (1000 chars), they're split into 
        overlapping chunks. This method fetches all chunks with the same 
        parent_message_id and reassembles them in order.
        
        Args:
            parent_message_id: The shared ID linking all chunks of a document
            collection: The Qdrant collection name
            
        Returns:
            Reconstructed document content, or None if reconstruction fails
        """
        try:
            # Fetch all chunks with this parent_message_id
            scroll_result = await db_manager.qdrant_client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="parent_message_id", match=MatchValue(value=parent_message_id)),
                        FieldCondition(key="is_chunk", match=MatchValue(value=True)),
                    ]
                ),
                limit=100,  # Should be enough for any document
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0] if scroll_result else []
            
            if not points:
                logger.debug(f"No chunks found for parent_message_id={parent_message_id}")
                return None
            
            # Sort chunks by chunk_index
            chunks: List[Dict[str, Any]] = []
            for point in points:
                payload = point.payload or {}
                chunks.append({
                    "index": payload.get("chunk_index", 0),
                    "content": payload.get("content", ""),
                    "total": payload.get("chunk_total", 1)
                })
            
            chunks.sort(key=lambda x: x["index"])
            
            # Verify we have all chunks
            expected_total = chunks[0]["total"] if chunks else 0
            if len(chunks) != expected_total:
                logger.warning(f"Chunk count mismatch: found {len(chunks)}, expected {expected_total}")
                # Continue anyway - partial reconstruction is better than nothing
            
            # Reconstruct content
            # Note: Chunks have 50-char overlap, so we need to deduplicate
            # For simplicity, we concatenate directly - the overlap is minimal
            # and won't significantly affect document reading
            reconstructed = ""
            for chunk in chunks:
                reconstructed += chunk["content"] + "\n"
            
            logger.info(f"Reconstructed document from {len(chunks)} chunks ({len(reconstructed)} chars)")
            return reconstructed.strip()
            
        except Exception as e:
            logger.error(f"Failed to reconstruct document from chunks: {e}")
            return None

    async def _arun(self, filename: str) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            
            # Strategy 1: Use metadata filter to find memories with attachments for this user
            # This is more reliable than semantic search for finding specific documents
            if db_manager.qdrant_client:
                try:
                    scroll_result = await db_manager.qdrant_client.scroll(
                        collection_name=collection,
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(key="user_id", match=MatchValue(value=str(self.user_id))),
                                FieldCondition(key="has_attachments", match=MatchValue(value=True)),
                            ]
                        ),
                        limit=20,  # Check recent document uploads
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    points = scroll_result[0] if scroll_result else []
                    
                    for point in points:
                        payload = point.payload or {}
                        filenames = payload.get("filenames", [])
                        content = payload.get("content", "")
                        
                        # Check if this memory contains our target filename
                        if filename in filenames or filename in content:
                            # Check if this is a chunked document
                            if payload.get("is_chunk") and payload.get("parent_message_id"):
                                reconstructed = await self._reconstruct_from_chunks(
                                    payload["parent_message_id"], 
                                    collection
                                )
                                if reconstructed:
                                    # Extract the specific file from reconstructed content
                                    extracted = self._extract_document_content(reconstructed, filename)
                                    if extracted:
                                        logger.info(f"Successfully extracted document '{filename}' via chunk reconstruction ({len(extracted)} chars)")
                                        return f"**Document: {filename}**\n\n{extracted}"
                            else:
                                # Non-chunked document - extract directly
                                extracted = self._extract_document_content(content, filename)
                                if extracted:
                                    logger.info(f"Successfully extracted document '{filename}' via metadata filter ({len(extracted)} chars)")
                                    return f"**Document: {filename}**\n\n{extracted}"
                    
                    logger.debug(f"Metadata filter found {len(points)} attachment memories, but none contained '{filename}'")
                    
                except Exception as e:
                    logger.warning(f"Metadata filter search failed, falling back to semantic search: {e}")
            
            # Strategy 2: Fall back to semantic search if metadata approach didn't work
            results = await memory_manager.search_memories(filename, self.user_id, limit=20, collection_name=collection)
            
            if not results:
                return f"Could not find document '{filename}' in memory. The document may not have been uploaded yet, or it might have been uploaded in a different conversation."
            
            # Look through results for the one with the actual file content
            for result in results:
                content = result.get('content', '')
                
                # Check if this is a chunked document
                if result.get('is_chunk') and result.get('parent_message_id'):
                    # Found a chunk that mentions our filename - try to reconstruct
                    reconstructed = await self._reconstruct_from_chunks(
                        result['parent_message_id'], 
                        collection
                    )
                    if reconstructed:
                        extracted = self._extract_document_content(reconstructed, filename)
                        if extracted:
                            logger.info(f"Successfully extracted document '{filename}' via chunk reconstruction from search ({len(extracted)} chars)")
                            return f"**Document: {filename}**\n\n{extracted}"
                
                # Check if this memory contains file content markers and our filename (non-chunked)
                elif "[Attached File Content]:" in content and filename in content:
                    extracted = self._extract_document_content(content, filename)
                    if extracted:
                        logger.info(f"Successfully extracted document '{filename}' via semantic search ({len(extracted)} chars)")
                        return f"**Document: {filename}**\n\n{extracted}"
            
            # Strategy 3: Try to find chunks directly by searching for the file header
            # This catches cases where the chunk with the header wasn't in top search results
            if db_manager.qdrant_client:
                try:
                    # Search for chunks that might contain our file header
                    header_search = f"--- File: {filename} ---"
                    header_results = await memory_manager.search_memories(
                        header_search, self.user_id, limit=5, collection_name=collection
                    )
                    
                    for result in header_results:
                        if result.get('is_chunk') and result.get('parent_message_id'):
                            reconstructed = await self._reconstruct_from_chunks(
                                result['parent_message_id'], 
                                collection
                            )
                            if reconstructed:
                                extracted = self._extract_document_content(reconstructed, filename)
                                if extracted:
                                    logger.info(f"Successfully extracted document '{filename}' via header search + reconstruction ({len(extracted)} chars)")
                                    return f"**Document: {filename}**\n\n{extracted}"
                except Exception as e:
                    logger.warning(f"Header search fallback failed: {e}")
            
            # If we found results but couldn't extract content
            logger.warning(f"Found {len(results)} memories mentioning '{filename}' but couldn't extract content")
            return f"Found references to '{filename}' but couldn't extract the full document content. The document preview you saw is the full content available. Use search_specific_memories to find specific details within the document."
            
        except Exception as e:
            logger.error(f"Error reading document '{filename}': {e}")
            return f"Error reading document: {str(e)}"
