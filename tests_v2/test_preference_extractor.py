import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.evolution.extractor import PreferenceExtractor, PreferenceResult

async def test_preference_extractor():
    logger.info("Starting Preference Extractor Test...")
    
    # ---------------------------------------------------------
    # Test 1: Extract Verbosity Preference
    # ---------------------------------------------------------
    logger.info("Test 1: Extract verbosity preference (Mocked)")
    
    mock_result = PreferenceResult(preferences={"verbosity": "short"})
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences("Please keep your answers short.")
        
        if prefs.get("verbosity") == "short":
            logger.info(f"✅ Verbosity preference extracted: {prefs}")
        else:
            logger.error(f"❌ Verbosity extraction failed: {prefs}")
    
    # ---------------------------------------------------------
    # Test 2: Extract Nickname
    # ---------------------------------------------------------
    logger.info("Test 2: Extract nickname preference")
    
    mock_result = PreferenceResult(preferences={"nickname": "Captain"})
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences("Call me Captain from now on.")
        
        if prefs.get("nickname") == "Captain":
            logger.info(f"✅ Nickname extracted: {prefs}")
        else:
            logger.error(f"❌ Nickname extraction failed: {prefs}")
    
    # ---------------------------------------------------------
    # Test 3: Extract Emoji Preference
    # ---------------------------------------------------------
    logger.info("Test 3: Extract emoji preference")
    
    mock_result = PreferenceResult(preferences={"use_emojis": False})
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences("I hate it when you use emojis.")
        
        if prefs.get("use_emojis") == False:
            logger.info(f"✅ Emoji preference extracted: {prefs}")
        else:
            logger.error(f"❌ Emoji preference extraction failed: {prefs}")
    
    # ---------------------------------------------------------
    # Test 4: Extract Style Preference
    # ---------------------------------------------------------
    logger.info("Test 4: Extract style preference")
    
    mock_result = PreferenceResult(preferences={"style": "formal"})
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences("Please be more professional in your responses.")
        
        if prefs.get("style") == "formal":
            logger.info(f"✅ Style preference extracted: {prefs}")
        else:
            logger.error(f"❌ Style extraction failed: {prefs}")
    
    # ---------------------------------------------------------
    # Test 5: No Preferences (Factual Statement)
    # ---------------------------------------------------------
    logger.info("Test 5: Handle factual statement without preferences")
    
    mock_result = PreferenceResult(preferences={})
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences("I like pizza.")
        
        if len(prefs) == 0:
            logger.info("✅ Correctly returned no preferences for factual statement")
        else:
            logger.error(f"❌ Should not extract preferences from facts: {prefs}")
    
    # ---------------------------------------------------------
    # Test 6: Multiple Preferences
    # ---------------------------------------------------------
    logger.info("Test 6: Extract multiple preferences")
    
    mock_result = PreferenceResult(preferences={
        "verbosity": "short",
        "use_emojis": True,
        "style": "casual"
    })
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences(
            "Keep it short and fun, and feel free to use emojis!"
        )
        
        if len(prefs) >= 2:
            logger.info(f"✅ Multiple preferences extracted: {prefs}")
        else:
            logger.error(f"❌ Multi-preference extraction failed: {prefs}")
    
    # ---------------------------------------------------------
    # Test 7: Error Handling
    # ---------------------------------------------------------
    logger.info("Test 7: Error handling when LLM fails")
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM API Error"))
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = PreferenceExtractor()
        prefs = await extractor.extract_preferences("This should fail gracefully")
        
        if len(prefs) == 0:
            logger.info("✅ Error handled gracefully, returned empty dict")
        else:
            logger.error(f"❌ Expected empty dict on error, got {prefs}")
    
    logger.info("✅ All Preference Extractor tests completed!")

if __name__ == "__main__":
    asyncio.run(test_preference_extractor())
