import os
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Optional
from loguru import logger
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

class DocumentProcessor:
    def __init__(self, temp_dir: str = "temp_downloads"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def process_local_file(self, file_path: Path) -> str:
        """
        Extracts text from a local file using LangChain loaders.
        """
        try:
            ext = file_path.suffix.lower()
            loader = None
            
            if ext == ".pdf":
                loader = PyPDFLoader(str(file_path))
            elif ext in [".docx", ".doc"]:
                loader = Docx2txtLoader(str(file_path))
            else:
                # Default to TextLoader for .txt, .md, .json, etc.
                # This might fail for binary files not handled above
                loader = TextLoader(str(file_path))
            
            # Run in executor to avoid blocking the event loop
            import asyncio
            loop = asyncio.get_running_loop()
            documents = await loop.run_in_executor(None, loader.load)
            
            # 3. Combine text
            full_text = "\n\n".join([doc.page_content for doc in documents])
            
            logger.info(f"Extracted {len(full_text)} characters from {file_path.name}")
            return full_text
        except Exception as e:
            logger.error(f"Document extraction failed for {file_path.name}: {e}")
            raise e

    async def process_attachment(self, attachment_url: str, filename: str) -> str:
        """
        Downloads a file from a URL and extracts its text content using LangChain.
        """
        file_path = self.temp_dir / filename
        
        try:
            # 1. Download the file
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment_url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download file: {resp.status}")
                        return f"Error: Could not download file {filename}."
                    
                    async with aiofiles.open(file_path, mode='wb') as f:
                        await f.write(await resp.read())
            
            logger.info(f"Downloaded file to {file_path}")

            return await self.process_local_file(file_path)

        except Exception as e:
            logger.error(f"Failed to process document {filename}: {e}")
            return f"Error processing file {filename}: {str(e)}"
            
        finally:
            # Cleanup
            if file_path.exists():
                try:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temp file {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")

# Global instance
document_processor = DocumentProcessor()
