import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.knowledge.extractor import FactExtractor, Fact, FactExtractionResult

async def test_fact_extractor():
    logger.info("Starting Fact Extractor Test...")
    
    # ---------------------------------------------------------
    # Test 1: Extract Simple Facts (Mocked LLM)
    # ---------------------------------------------------------
    logger.info("Test 1: Extract facts from simple statement (Mocked)")
    
    mock_result = FactExtractionResult(facts=[
        Fact(subject="User", predicate="LIVES_IN", object="Seattle", confidence=0.95),
        Fact(subject="User", predicate="HAS_PET_NAMED", object="Max", confidence=0.9),
        Fact(subject="Max", predicate="IS_A", object="Dog", confidence=1.0)
    ])
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = FactExtractor()
        facts = await extractor.extract_facts("I live in Seattle and my dog's name is Max.")
        
        if len(facts) == 3:
            logger.info(f"✅ Extracted {len(facts)} facts")
            subjects = [f.subject for f in facts]
            predicates = [f.predicate for f in facts]
            objects = [f.object for f in facts]
            
            if "User" in subjects and "LIVES_IN" in predicates and "Seattle" in objects:
                logger.info("✅ Location fact extracted correctly")
            else:
                logger.error("❌ Location fact extraction failed")
            
            if "HAS_PET_NAMED" in predicates and "Max" in objects:
                logger.info("✅ Pet name fact extracted correctly")
            else:
                logger.error("❌ Pet name fact extraction failed")
            
            if "IS_A" in predicates and "Dog" in objects:
                logger.info("✅ Pet type fact extracted correctly")
            else:
                logger.error("❌ Pet type fact extraction failed")
        else:
            logger.error(f"❌ Expected 3 facts, got {len(facts)}")
    
    # ---------------------------------------------------------
    # Test 2: No Facts to Extract
    # ---------------------------------------------------------
    logger.info("Test 2: Handle message with no extractable facts")
    
    mock_empty_result = FactExtractionResult(facts=[])
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_empty_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = FactExtractor()
        facts = await extractor.extract_facts("How are you today?")
        
        if len(facts) == 0:
            logger.info("✅ Correctly returned no facts for transient query")
        else:
            logger.error(f"❌ Expected 0 facts, got {len(facts)}")
    
    # ---------------------------------------------------------
    # Test 3: Complex Facts with Multiple Subjects
    # ---------------------------------------------------------
    logger.info("Test 3: Extract facts with multiple subjects")
    
    mock_complex_result = FactExtractionResult(facts=[
        Fact(subject="User", predicate="LIKES", object="Pizza", confidence=0.85),
        Fact(subject="User", predicate="WORKS_AS", object="Software Engineer", confidence=0.9),
        Fact(subject="User", predicate="STUDIES_AT", object="MIT", confidence=0.95)
    ])
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_complex_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = FactExtractor()
        facts = await extractor.extract_facts(
            "I'm a software engineer who studied at MIT and I love pizza."
        )
        
        if len(facts) == 3:
            logger.info(f"✅ Extracted {len(facts)} complex facts")
            predicates = [f.predicate for f in facts]
            if "LIKES" in predicates and "WORKS_AS" in predicates and "STUDIES_AT" in predicates:
                logger.info("✅ All predicates extracted correctly")
            else:
                logger.error(f"❌ Predicate extraction incomplete: {predicates}")
        else:
            logger.error(f"❌ Expected 3 facts, got {len(facts)}")
    
    # ---------------------------------------------------------
    # Test 4: Error Handling
    # ---------------------------------------------------------
    logger.info("Test 4: Error handling when LLM fails")
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM API Error"))
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = FactExtractor()
        facts = await extractor.extract_facts("This should fail gracefully")
        
        if len(facts) == 0:
            logger.info("✅ Error handled gracefully, returned empty list")
        else:
            logger.error(f"❌ Expected 0 facts on error, got {len(facts)}")
    
    # ---------------------------------------------------------
    # Test 5: Fact Confidence Scores
    # ---------------------------------------------------------
    logger.info("Test 5: Verify confidence scores")
    
    mock_confidence_result = FactExtractionResult(facts=[
        Fact(subject="User", predicate="LIKES", object="Chocolate", confidence=1.0),
        Fact(subject="User", predicate="MIGHT_LIKE", object="Vanilla", confidence=0.5)
    ])
    
    with patch('src_v2.agents.llm_factory.create_llm') as mock_create_llm:
        mock_base_llm = AsyncMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_confidence_result)
        mock_base_llm.with_structured_output.return_value = mock_structured_llm
        mock_create_llm.return_value = mock_base_llm
        
        extractor = FactExtractor()
        facts = await extractor.extract_facts("I definitely like chocolate, maybe vanilla too.")
        
        if len(facts) == 2:
            high_confidence = [f for f in facts if f.confidence >= 0.8]
            low_confidence = [f for f in facts if f.confidence < 0.8]
            
            if len(high_confidence) >= 1 and len(low_confidence) >= 1:
                logger.info(f"✅ Confidence scores vary appropriately: {[f.confidence for f in facts]}")
            else:
                logger.warning(f"⚠️ Confidence distribution may not be ideal: {[f.confidence for f in facts]}")
        else:
            logger.error(f"❌ Expected 2 facts, got {len(facts)}")
    
    logger.info("✅ All Fact Extractor tests completed!")

if __name__ == "__main__":
    asyncio.run(test_fact_extractor())
