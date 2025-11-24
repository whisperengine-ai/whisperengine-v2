import asyncio
import sys
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.knowledge.documents import DocumentProcessor

async def test_document_processor():
    logger.info("Starting Document Processor Test...")
    
    # Ensure temp dir exists
    temp_dir = Path("temp_test_docs")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(exist_ok=True)
    
    processor = DocumentProcessor(temp_dir=str(temp_dir))

    # ---------------------------------------------------------
    # 1. Test Text File Processing (Real file)
    # ---------------------------------------------------------
    logger.info("Test 1: Processing .txt file")
    txt_path = temp_dir / "test.txt"
    with open(txt_path, "w") as f:
        f.write("Hello, this is a test document.")
    
    try:
        content = await processor.process_local_file(txt_path)
        if "Hello, this is a test document." in content:
            logger.info("✅ Text file processing passed.")
        else:
            logger.error(f"❌ Text file processing failed. Got: {content}")
    except Exception as e:
        logger.error(f"❌ Text file processing raised exception: {e}")

    # ---------------------------------------------------------
    # 2. Test PDF Processing (Mocked Loader)
    # ---------------------------------------------------------
    logger.info("Test 2: Processing .pdf file (Mocked)")
    pdf_path = temp_dir / "test.pdf"
    # Create dummy file so path exists and suffix detection works
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy content")

    # We need to mock PyPDFLoader inside the module
    with patch("src_v2.knowledge.documents.PyPDFLoader") as MockLoader:
        # Setup mock
        mock_instance = MockLoader.return_value
        # The loader.load method is run in executor, so it's synchronous
        mock_doc = MagicMock()
        mock_doc.page_content = "PDF Content Extracted"
        mock_instance.load.return_value = [mock_doc]
        
        try:
            content = await processor.process_local_file(pdf_path)
            if "PDF Content Extracted" in content:
                logger.info("✅ PDF processing passed.")
            else:
                logger.error(f"❌ PDF processing failed. Got: {content}")
        except Exception as e:
            logger.error(f"❌ PDF processing raised exception: {e}")

    # ---------------------------------------------------------
    # 3. Test Attachment Download & Process (Mocked Network)
    # ---------------------------------------------------------
    logger.info("Test 3: Attachment Download (Mocked)")
    
    with patch("aiohttp.ClientSession") as MockSession:
        # Mock the session instance (must be MagicMock, not AsyncMock, to avoid auto-coroutine on .get)
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # When ClientSession() is instantiated, return our mock session
        MockSession.return_value = mock_session
        
        # Mock the response
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"Remote Content"
        
        # Mock session.get() context manager
        mock_get_ctx = MagicMock()
        mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_get_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_session.get.return_value = mock_get_ctx
        
        # We simulate downloading a .txt file so we don't need to mock the loader again
        # (TextLoader works on the real file we write)
        url = "http://example.com/remote.txt"
        filename = "remote.txt"
        
        try:
            content = await processor.process_attachment(url, filename)
            
            if "Remote Content" in content:
                logger.info("✅ Attachment processing passed.")
            else:
                logger.error(f"❌ Attachment processing failed. Got: {content}")
        except Exception as e:
            logger.error(f"❌ Attachment processing raised exception: {e}")

    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    logger.info("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(test_document_processor())
