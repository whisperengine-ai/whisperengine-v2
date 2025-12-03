
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.memory.manager import memory_manager
from src_v2.config.settings import settings

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

    async def _arun(self, filename: str) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            
            # Strategy 1: Search for the filename directly (most recent memories)
            results = await memory_manager.search_memories(filename, self.user_id, limit=10, collection_name=collection)
            
            if not results:
                return f"Could not find document '{filename}' in memory. The document may not have been uploaded yet, or it might have been uploaded in a different conversation."
            
            # Look through results for the one with the actual file content
            for result in results:
                content = result.get('content', '')
                
                # Check if this memory contains file content markers
                if "[Attached File Content]:" in content:
                    # This is a memory with document content
                    # Look for our specific filename
                    if filename in content:
                        # Found it! Now extract the content between markers
                        # Format: "--- File: filename ---\nContent..."
                        
                        # Try both marker formats
                        marker = f"--- File: {filename} ---"
                        if marker not in content:
                            marker = f"--- Referenced File: {filename} ---"
                        
                        if marker in content:
                            # Split and get content after marker
                            parts = content.split(marker, 1)
                            if len(parts) > 1:
                                file_content = parts[1].strip()
                                
                                # Remove any subsequent file markers (if multiple files)
                                if "--- File:" in file_content:
                                    file_content = file_content.split("--- File:")[0].strip()
                                if "--- Referenced File:" in file_content:
                                    file_content = file_content.split("--- Referenced File:")[0].strip()
                                
                                # Remove trailing metadata if present
                                if "[Attached File Content]:" in file_content:
                                    file_content = file_content.split("[Attached File Content]:")[0].strip()
                                    
                                logger.info(f"Successfully extracted document '{filename}' ({len(file_content)} chars)")
                                return f"**Document: {filename}**\n\n{file_content}"
            
            # If we found results but couldn't extract content
            logger.warning(f"Found {len(results)} memories mentioning '{filename}' but couldn't extract content")
            return f"Found references to '{filename}' but couldn't extract the full document content. The document preview you saw is the full content available. Use search_specific_memories to find specific details within the document."
            
        except Exception as e:
            logger.error(f"Error reading document '{filename}': {e}")
            return f"Error reading document: {str(e)}"
