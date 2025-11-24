import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings

async def test_llm_factory():
    logger.info("Starting LLM Factory Test...")
    
    # ---------------------------------------------------------
    # Test 1: Create Main LLM
    # ---------------------------------------------------------
    logger.info("Test 1: Create main LLM instance")
    
    try:
        llm = create_llm(temperature=0.7, mode="main")
        
        if llm:
            logger.info(f"✅ Main LLM created: {type(llm).__name__}")
            
            # Check if it has expected attributes
            if hasattr(llm, 'temperature'):
                logger.info(f"✅ Temperature set: {llm.temperature}")
            else:
                logger.warning("⚠️ Temperature attribute not found")
            
            if hasattr(llm, 'model_name') or hasattr(llm, 'model'):
                model_name = getattr(llm, 'model_name', getattr(llm, 'model', 'unknown'))
                logger.info(f"✅ Model name: {model_name}")
            else:
                logger.warning("⚠️ Model name not accessible")
        else:
            logger.error("❌ Failed to create main LLM")
    except Exception as e:
        logger.error(f"❌ Error creating main LLM: {e}")
    
    # ---------------------------------------------------------
    # Test 2: Create Router LLM (if configured)
    # ---------------------------------------------------------
    logger.info("Test 2: Create router LLM instance")
    
    try:
        router_llm = create_llm(temperature=0.0, mode="router")
        
        if router_llm:
            logger.info(f"✅ Router LLM created: {type(router_llm).__name__}")
            
            if hasattr(router_llm, 'temperature'):
                if router_llm.temperature == 0.0:
                    logger.info("✅ Router LLM has correct low temperature")
                else:
                    logger.warning(f"⚠️ Router LLM temperature is {router_llm.temperature}, expected 0.0")
        else:
            logger.error("❌ Failed to create router LLM")
    except Exception as e:
        logger.info(f"ℹ️ Router LLM not configured or error: {e}")
    
    # ---------------------------------------------------------
    # Test 3: Create Reflective LLM (if configured)
    # ---------------------------------------------------------
    logger.info("Test 3: Create reflective LLM instance")
    
    try:
        reflective_llm = create_llm(temperature=0.3, mode="reflective")
        
        if reflective_llm:
            logger.info(f"✅ Reflective LLM created: {type(reflective_llm).__name__}")
        else:
            logger.error("❌ Failed to create reflective LLM")
    except Exception as e:
        logger.info(f"ℹ️ Reflective LLM not configured or error: {e}")
    
    # ---------------------------------------------------------
    # Test 4: Create Utility LLM
    # ---------------------------------------------------------
    logger.info("Test 4: Create utility LLM instance")
    
    try:
        utility_llm = create_llm(temperature=0.0, mode="utility")
        
        if utility_llm:
            logger.info(f"✅ Utility LLM created: {type(utility_llm).__name__}")
        else:
            logger.error("❌ Failed to create utility LLM")
    except Exception as e:
        logger.error(f"❌ Error creating utility LLM: {e}")
    
    # ---------------------------------------------------------
    # Test 5: Temperature Override
    # ---------------------------------------------------------
    logger.info("Test 5: Test temperature override")
    
    try:
        llm_low_temp = create_llm(temperature=0.1, mode="main")
        llm_high_temp = create_llm(temperature=1.5, mode="main")
        
        if hasattr(llm_low_temp, 'temperature') and hasattr(llm_high_temp, 'temperature'):
            if llm_low_temp.temperature == 0.1 and llm_high_temp.temperature == 1.5:
                logger.info("✅ Temperature override works correctly")
            else:
                logger.warning(f"⚠️ Temperature override may not work (got {llm_low_temp.temperature} and {llm_high_temp.temperature})")
        else:
            logger.warning("⚠️ Cannot verify temperature override")
    except Exception as e:
        logger.error(f"❌ Error testing temperature override: {e}")
    
    # ---------------------------------------------------------
    # Test 6: Provider Configuration
    # ---------------------------------------------------------
    logger.info("Test 6: Verify provider configuration")
    
    provider = settings.LLM_PROVIDER
    logger.info(f"ℹ️ Configured provider: {provider}")
    
    if provider in ["openai", "openrouter", "lmstudio", "ollama"]:
        logger.info(f"✅ Valid provider: {provider}")
    else:
        logger.warning(f"⚠️ Unknown provider: {provider}")
    
    # ---------------------------------------------------------
    # Test 7: Test Different Providers (Mocked)
    # ---------------------------------------------------------
    logger.info("Test 7: Test provider switching (Mocked)")
    
    original_provider = settings.LLM_PROVIDER
    
    # Test OpenAI provider
    with patch.object(settings, 'LLM_PROVIDER', 'openai'):
        try:
            llm = create_llm(mode="main")
            if llm:
                logger.info(f"✅ OpenAI provider works: {type(llm).__name__}")
        except Exception as e:
            logger.warning(f"⚠️ OpenAI provider test failed: {e}")
    
    # Test OpenRouter provider
    with patch.object(settings, 'LLM_PROVIDER', 'openrouter'):
        with patch.object(settings, 'LLM_BASE_URL', 'https://openrouter.ai/api/v1'):
            try:
                llm = create_llm(mode="main")
                if llm:
                    logger.info(f"✅ OpenRouter provider works: {type(llm).__name__}")
            except Exception as e:
                logger.warning(f"⚠️ OpenRouter provider test failed: {e}")
    
    # Test Ollama provider (may not be available)
    with patch.object(settings, 'LLM_PROVIDER', 'ollama'):
        try:
            llm = create_llm(mode="main")
            if llm:
                logger.info(f"✅ Ollama provider works: {type(llm).__name__}")
        except Exception as e:
            logger.info(f"ℹ️ Ollama provider not available: {e}")
    
    # ---------------------------------------------------------
    # Test 8: Invalid Provider Handling
    # ---------------------------------------------------------
    logger.info("Test 8: Handle invalid provider")
    
    with patch.object(settings, 'LLM_PROVIDER', 'invalid_provider'):
        try:
            llm = create_llm(mode="main")
            logger.error("❌ Should have raised error for invalid provider")
        except ValueError as e:
            logger.info(f"✅ Invalid provider correctly rejected: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Unexpected error for invalid provider: {e}")
    
    logger.info("✅ All LLM Factory tests completed!")

if __name__ == "__main__":
    asyncio.run(test_llm_factory())
