import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.memory.summarizer import SummaryManager, SummaryResult

async def test_summarizer():
    logger.info("Starting Summarizer Test...")
    
    summarizer = SummaryManager()
    
    # ---------------------------------------------------------
    # Test 1: Generate Summary from Simple Conversation
    # ---------------------------------------------------------
    logger.info("Test 1: Generate summary from conversation (Mocked)")
    
    messages = [
        {"role": "user", "content": "I went hiking last weekend"},
        {"role": "assistant", "content": "That sounds wonderful! Where did you go?"},
        {"role": "user", "content": "To Yosemite. The views were incredible."}
    ]
    
    mock_result = SummaryResult(
        summary="User went hiking in Yosemite and enjoyed the views.",
        meaningfulness_score=3,
        emotions=["excited", "happy"]
    )
    
    with patch.object(summarizer.chain, 'ainvoke', new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = mock_result
        
        result = await summarizer.generate_summary(messages)
        
        if result and result.summary:
            logger.info(f"✅ Summary generated: {result.summary}")
            logger.info(f"   Meaningfulness: {result.meaningfulness_score}/5")
            logger.info(f"   Emotions: {result.emotions}")
        else:
            logger.error("❌ Summary generation failed")
    
    # ---------------------------------------------------------
    # Test 2: High Meaningfulness Conversation
    # ---------------------------------------------------------
    logger.info("Test 2: Deep conversation with high meaningfulness")
    
    messages = [
        {"role": "user", "content": "I've been thinking a lot about my career lately"},
        {"role": "assistant", "content": "That's a big topic. What's on your mind?"},
        {"role": "user", "content": "I'm not sure if I'm on the right path. I feel unfulfilled."}
    ]
    
    mock_result = SummaryResult(
        summary="User is questioning their career path and feeling unfulfilled.",
        meaningfulness_score=5,
        emotions=["contemplative", "uncertain", "anxious"]
    )
    
    with patch.object(summarizer.chain, 'ainvoke', new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = mock_result
        
        result = await summarizer.generate_summary(messages)
        
        if result and result.meaningfulness_score >= 4:
            logger.info(f"✅ High meaningfulness detected: {result.meaningfulness_score}/5")
        else:
            logger.error(f"❌ Expected high meaningfulness, got {result.meaningfulness_score if result else 'None'}")
    
    # ---------------------------------------------------------
    # Test 3: Low Meaningfulness (Small Talk)
    # ---------------------------------------------------------
    logger.info("Test 3: Small talk with low meaningfulness")
    
    messages = [
        {"role": "user", "content": "Hi!"},
        {"role": "assistant", "content": "Hello! How are you?"},
        {"role": "user", "content": "Good, you?"}
    ]
    
    mock_result = SummaryResult(
        summary="Casual greeting exchange.",
        meaningfulness_score=1,
        emotions=["friendly", "neutral"]
    )
    
    with patch.object(summarizer.chain, 'ainvoke', new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = mock_result
        
        result = await summarizer.generate_summary(messages)
        
        if result and result.meaningfulness_score <= 2:
            logger.info(f"✅ Low meaningfulness for small talk: {result.meaningfulness_score}/5")
        else:
            logger.error(f"❌ Small talk should have low score, got {result.meaningfulness_score if result else 'None'}")
    
    # ---------------------------------------------------------
    # Test 4: Empty Message List
    # ---------------------------------------------------------
    logger.info("Test 4: Handle empty message list")
    
    result = await summarizer.generate_summary([])
    
    if result is None:
        logger.info("✅ Correctly returned None for empty messages")
    else:
        logger.error(f"❌ Should return None for empty messages, got {result}")
    
    # ---------------------------------------------------------
    # Test 5: Emotion Detection
    # ---------------------------------------------------------
    logger.info("Test 5: Verify emotion detection")
    
    messages = [
        {"role": "user", "content": "I'm so frustrated with my job!"},
        {"role": "assistant", "content": "I hear you. That sounds really difficult."}
    ]
    
    mock_result = SummaryResult(
        summary="User is frustrated with their job.",
        meaningfulness_score=3,
        emotions=["frustrated", "stressed"]
    )
    
    with patch.object(summarizer.chain, 'ainvoke', new_callable=AsyncMock) as mock_chain:
        mock_chain.return_value = mock_result
        
        result = await summarizer.generate_summary(messages)
        
        if result and "frustrated" in result.emotions:
            logger.info(f"✅ Emotions correctly detected: {result.emotions}")
        else:
            logger.error(f"❌ Emotion detection failed: {result.emotions if result else 'None'}")
    
    # ---------------------------------------------------------
    # Test 6: Error Handling
    # ---------------------------------------------------------
    logger.info("Test 6: Error handling when summarization fails")
    
    with patch.object(summarizer.chain, 'ainvoke', new_callable=AsyncMock) as mock_chain:
        mock_chain.side_effect = Exception("LLM API Error")
        
        result = await summarizer.generate_summary(messages)
        
        if result is None:
            logger.info("✅ Error handled gracefully, returned None")
        else:
            logger.error(f"❌ Expected None on error, got {result}")
    
    logger.info("✅ All Summarizer tests completed!")

if __name__ == "__main__":
    asyncio.run(test_summarizer())
