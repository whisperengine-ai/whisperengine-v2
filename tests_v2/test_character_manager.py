import asyncio
import sys
import os
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.core.character import character_manager, Character

async def test_character_manager():
    logger.info("Starting Character Manager Test...")
    
    # ---------------------------------------------------------
    # Test 1: Load Character
    # ---------------------------------------------------------
    logger.info("Test 1: Load character from disk")
    
    # Elena should exist in characters/ directory
    character = character_manager.get_character("elena")
    
    if character:
        logger.info(f"✅ Character loaded: {character.name}")
        
        # Verify required attributes
        if hasattr(character, 'system_prompt') and character.system_prompt:
            logger.info("✅ System prompt exists")
        else:
            logger.error("❌ System prompt missing")
        
        if hasattr(character, 'personality_traits') and character.personality_traits:
            logger.info(f"✅ Personality traits loaded: {list(character.personality_traits.keys())[:3]}...")
        else:
            logger.warning("⚠️ Personality traits may be empty")
        
        if hasattr(character, 'voice_id'):
            logger.info(f"✅ Voice ID configured: {character.voice_id if character.voice_id else 'None'}")
        else:
            logger.warning("⚠️ Voice ID not configured")
    else:
        logger.error("❌ Failed to load character 'elena'")
        return
    
    # ---------------------------------------------------------
    # Test 2: Character Caching
    # ---------------------------------------------------------
    logger.info("Test 2: Test character caching")
    
    character2 = character_manager.get_character("elena")
    
    if character is character2:
        logger.info("✅ Character caching works (same object returned)")
    else:
        logger.warning("⚠️ Character caching may not be working (different object)")
    
    # ---------------------------------------------------------
    # Test 3: List Available Characters
    # ---------------------------------------------------------
    logger.info("Test 3: List available characters")
    
    characters_dir = Path("characters")
    if characters_dir.exists():
        character_dirs = [d.name for d in characters_dir.iterdir() if d.is_dir() and (d / "character.md").exists()]
        
        if len(character_dirs) > 0:
            logger.info(f"✅ Found {len(character_dirs)} characters: {character_dirs[:5]}")
        else:
            logger.error("❌ No characters found")
    else:
        logger.error("❌ Characters directory not found")
    
    # ---------------------------------------------------------
    # Test 4: Character System Prompt Structure
    # ---------------------------------------------------------
    logger.info("Test 4: Validate system prompt structure")
    
    if character:
        system_prompt = character.system_prompt
        
        # Check for key components
        has_name = character.name.lower() in system_prompt.lower()
        has_personality = "personality" in system_prompt.lower() or "traits" in system_prompt.lower()
        has_instructions = len(system_prompt) > 100  # Should be substantial
        
        if has_name:
            logger.info("✅ System prompt contains character name")
        else:
            logger.warning("⚠️ System prompt may not contain character name")
        
        if has_personality:
            logger.info("✅ System prompt references personality")
        else:
            logger.warning("⚠️ System prompt may not reference personality")
        
        if has_instructions:
            logger.info(f"✅ System prompt has substantial content ({len(system_prompt)} chars)")
        else:
            logger.warning(f"⚠️ System prompt may be too short ({len(system_prompt)} chars)")
    
    # ---------------------------------------------------------
    # Test 5: Character Background (if available)
    # ---------------------------------------------------------
    logger.info("Test 5: Check for character background")
    
    background_file = Path(f"characters/elena/background.yaml")
    if background_file.exists():
        logger.info("✅ Background file exists")
        
        import yaml
        try:
            with open(background_file, 'r') as f:
                background = yaml.safe_load(f)
            
            if background and 'facts' in background:
                logger.info(f"✅ Background contains {len(background['facts'])} facts")
            else:
                logger.warning("⚠️ Background file may not contain facts")
        except Exception as e:
            logger.error(f"❌ Failed to parse background YAML: {e}")
    else:
        logger.info("ℹ️ No background file (optional)")
    
    # ---------------------------------------------------------
    # Test 6: Load Non-Existent Character
    # ---------------------------------------------------------
    logger.info("Test 6: Handle non-existent character gracefully")
    
    fake_character = character_manager.get_character("nonexistent_character_xyz")
    
    if fake_character is None:
        logger.info("✅ Correctly returns None for non-existent character")
    else:
        logger.error("❌ Should return None for non-existent character")
    
    # ---------------------------------------------------------
    # Test 7: Character Personality Traits Access
    # ---------------------------------------------------------
    logger.info("Test 7: Access personality traits")
    
    if character and hasattr(character, 'personality_traits'):
        traits = character.personality_traits
        
        if isinstance(traits, dict):
            logger.info(f"✅ Personality traits is a dictionary with {len(traits)} entries")
            
            # Check for common trait keys
            expected_keys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
            found_keys = [k for k in expected_keys if k in traits]
            
            if len(found_keys) > 0:
                logger.info(f"✅ Found personality dimensions: {found_keys}")
            else:
                logger.warning(f"⚠️ Standard personality dimensions not found. Keys: {list(traits.keys())[:5]}")
        else:
            logger.error(f"❌ Personality traits should be dict, got {type(traits)}")
    
    logger.info("✅ All Character Manager tests completed!")

if __name__ == "__main__":
    asyncio.run(test_character_manager())
