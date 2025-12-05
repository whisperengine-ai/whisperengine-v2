
from typing import Type, Optional
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
                            # Try to extract the document content
                            extracted = self._extract_document_content(content, filename)
                            if extracted:
                                logger.info(f"Successfully extracted document '{filename}' via metadata filter ({len(extracted)} chars)")
                                return f"**Document: {filename}**\n\n{extracted}"
                    
                    logger.debug(f"Metadata filter found {len(points)} attachment memories, but none contained '{filename}'")
                    
                except Exception as e:
                    logger.warning(f"Metadata filter search failed, falling back to semantic search: {e}")
            
            # Strategy 2: Fall back to semantic search if metadata approach didn't work
            results = await memory_manager.search_memories(filename, self.user_id, limit=15, collection_name=collection)
            
            if not results:
                return f"Could not find document '{filename}' in memory. The document may not have been uploaded yet, or it might have been uploaded in a different conversation."
            
            # Look through results for the one with the actual file content
            for result in results:
                content = result.get('content', '')
                
                # Check if this memory contains file content markers and our filename
                if "[Attached File Content]:" in content and filename in content:
                    extracted = self._extract_document_content(content, filename)
                    if extracted:
                        logger.info(f"Successfully extracted document '{filename}' via semantic search ({len(extracted)} chars)")
                        return f"**Document: {filename}**\n\n{extracted}"
            
            # If we found results but couldn't extract content
            logger.warning(f"Found {len(results)} memories mentioning '{filename}' but couldn't extract content")
            return f"Found references to '{filename}' but couldn't extract the full document content. The document preview you saw is the full content available. Use search_specific_memories to find specific details within the document."
            
        except Exception as e:
            logger.error(f"Error reading document '{filename}': {e}")
            return f"Error reading document: {str(e)}"
