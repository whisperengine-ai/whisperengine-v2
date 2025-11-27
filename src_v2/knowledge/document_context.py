"""
Document Context - Clean abstraction for document handling in conversations.

This module provides a single source of truth for document-related context,
replacing scattered string-matching and inline logic throughout the codebase.
"""
from dataclasses import dataclass, field
from typing import List
import re
from loguru import logger


@dataclass
class DocumentContext:
    """
    Represents processed documents attached to a message.
    
    This provides a clean interface for document handling:
    - Full content stored in memory for RAG
    - Preview sent to LLM for immediate response
    - Metadata for classification and retrieval
    """
    filenames: List[str] = field(default_factory=list)
    full_content: str = ""
    preview_content: str = ""
    has_documents: bool = False
    
    # Configurable limits
    PREVIEW_LIMIT: int = 2000  # Chars to send to LLM
    
    @classmethod
    def from_processed_files(cls, processed_files: List[str]) -> "DocumentContext":
        """
        Creates DocumentContext from processed file content strings.
        
        Args:
            processed_files: List of strings like "--- File: name.pdf ---\nContent..."
            
        Returns:
            DocumentContext with extracted metadata and content
        """
        if not processed_files:
            return cls()
        
        # Combine all file content
        full_content = "\n\n".join(processed_files)
        
        # Extract filenames from headers
        filenames = re.findall(r'--- (?:File|Referenced File): (.+?) ---', full_content)
        
        # Create preview
        preview_content = full_content[:cls.PREVIEW_LIMIT]
        if len(full_content) > cls.PREVIEW_LIMIT:
            remaining = len(full_content) - cls.PREVIEW_LIMIT
            preview_content += f"\n...[Content continues - {remaining} more chars stored in memory]..."
        
        logger.info(f"Document context: {len(filenames)} files, {len(preview_content)} preview / {len(full_content)} full chars")
        
        return cls(
            filenames=filenames,
            full_content=full_content,
            preview_content=preview_content,
            has_documents=True
        )
    
    def format_for_llm(self) -> str:
        """
        Formats document context for inclusion in LLM message.
        
        Returns:
            Formatted string with preview and retrieval hint
        """
        if not self.has_documents:
            return ""
        
        filename_list = ", ".join(self.filenames) if self.filenames else "uploaded documents"
        
        return (
            f"\n\n[Attached Files: {filename_list}]\n"
            f"{self.preview_content}\n\n"
            f"(Full document content has been stored in memory. "
            f"Use search_specific_memories tool to find more details if needed.)"
        )
    
    def format_for_memory(self, user_message: str) -> str:
        """
        Formats document context for memory storage (includes full content).
        
        Args:
            user_message: The original user message
            
        Returns:
            Message with full document content appended
        """
        if not self.has_documents:
            return user_message
        
        return f"{user_message}\n\n[Attached File Content]:\n{self.full_content}"
    
    def get_memory_metadata(self) -> dict:
        """
        Returns metadata for memory storage.
        
        Returns:
            Dict with attachment metadata
        """
        if not self.has_documents:
            return {}
        
        return {
            "has_attachments": True,
            "filenames": self.filenames
        }


def has_document_context(message_content: str) -> bool:
    """
    Checks if a message contains document context markers.
    
    This is a utility for checking chat history without needing
    to parse the full document structure.
    
    Args:
        message_content: Message text to check
        
    Returns:
        True if message contains document markers
    """
    markers = [
        "[Attached Files:",
        "[Attached File Content]:",
        "[Visual Memory]"
    ]
    return any(marker in message_content for marker in markers)


def history_has_document_context(chat_history: list) -> bool:
    """
    Checks if recent chat history involves documents.
    
    Args:
        chat_history: List of BaseMessage objects
        
    Returns:
        True if any recent message contains document context
    """
    for msg in chat_history:
        if hasattr(msg, 'content') and isinstance(msg.content, str):
            if has_document_context(msg.content):
                return True
    return False
