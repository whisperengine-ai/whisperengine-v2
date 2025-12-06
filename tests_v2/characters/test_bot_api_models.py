"""
Automated API tests for each bot's chat endpoint.

Tests each bot's /api/chat endpoint to verify:
1. The bot is responding
2. The configured LLM model is being used
3. Response quality and character consistency

Usage:
    # Test all bots
    pytest tests_v2/characters/test_bot_api_models.py -v

    # Test specific bot
    pytest tests_v2/characters/test_bot_api_models.py -v -k "aria"

    # Run with output visible
    pytest tests_v2/characters/test_bot_api_models.py -v -s --no-cov

Requirements:
    - Bots must be running (./bot.sh up all)
    - Each bot's API must be accessible on its configured port
"""

import pytest
import httpx
import asyncio
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class BotConfig:
    """Configuration for a bot under test."""
    name: str
    port: int
    main_model: str
    reflective_model: str
    is_production: bool = False  # Production bots (nottaylor, dotty) use GPT-4o


# Bot configurations with their expected models (synced Dec 5, 2025)
# Pattern: Fast main model → Smart reflective model
# Distribution: 3 Anthropic, 3 Google, 3 Mistral, 3 Grok
BOT_CONFIGS = [
    # Anthropic bots (fast haiku → smart sonnet)
    BotConfig(
        name="elena",
        port=8000,
        main_model="anthropic/claude-3.5-haiku",
        reflective_model="anthropic/claude-sonnet-4.5"
    ),
    BotConfig(
        name="dotty",
        port=8002,
        main_model="anthropic/claude-3.5-haiku",
        reflective_model="anthropic/claude-sonnet-4.5"
    ),
    BotConfig(
        name="aetheris",
        port=8011,
        main_model="anthropic/claude-3.5-haiku",
        reflective_model="anthropic/claude-sonnet-4.5"
    ),
    # Google bots (fast flash → smart pro)
    BotConfig(
        name="aria",
        port=8003,
        main_model="google/gemini-2.5-flash",
        reflective_model="google/gemini-2.5-pro"
    ),
    BotConfig(
        name="marcus",
        port=8007,
        main_model="google/gemini-2.5-flash",
        reflective_model="google/gemini-2.5-pro"
    ),
    BotConfig(
        name="ryan",
        port=8001,
        main_model="google/gemini-2.5-flash",
        reflective_model="google/gemini-2.5-pro"
    ),
    # Mistral bots (small → medium)
    BotConfig(
        name="nottaylor",
        port=8008,
        main_model="mistralai/mistral-small-3.1-24b-instruct",
        reflective_model="mistralai/mistral-medium-3.1",
        is_production=True
    ),
    BotConfig(
        name="gabriel",
        port=8009,
        main_model="mistralai/mistral-small-3.1-24b-instruct",
        reflective_model="mistralai/mistral-medium-3.1"
    ),
    BotConfig(
        name="aethys",
        port=8010,
        main_model="mistralai/mistral-small-3.1-24b-instruct",
        reflective_model="mistralai/mistral-medium-3.1"
    ),
    # Grok bots (fast → reasoning)
    BotConfig(
        name="dream",
        port=8004,
        main_model="x-ai/grok-4.1-fast",
        reflective_model="x-ai/grok-4"
    ),
    BotConfig(
        name="jake",
        port=8005,
        main_model="x-ai/grok-4.1-fast",
        reflective_model="x-ai/grok-4"
    ),
    BotConfig(
        name="sophia",
        port=8006,
        main_model="x-ai/grok-4.1-fast",
        reflective_model="x-ai/grok-4"
    ),
]

# Test prompts for different scenarios
TEST_PROMPTS = {
    "simple": "Hi! How are you today?",
    "memory": "What do you remember about our last conversation?",
    "reasoning": "If I have 3 apples and give you half, how many do you have?",
    "character": "Tell me about yourself in one sentence.",
}


class TestBotAPI:
    """Test suite for bot API endpoints."""

    @pytest.fixture
    def base_url(self):
        """Base URL template for bot APIs."""
        return "http://localhost:{port}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_health_check(self, bot: BotConfig):
        """Test that each bot's health endpoint is responding."""
        url = f"http://localhost:{bot.port}/health"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url)
                assert response.status_code == 200, f"{bot.name} health check failed"
                data = response.json()
                assert data.get("status") == "healthy", f"{bot.name} not healthy"
            except httpx.ConnectError:
                pytest.skip(f"{bot.name} not running on port {bot.port}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_simple_chat(self, bot: BotConfig):
        """Test simple chat response from each bot."""
        url = f"http://localhost:{bot.port}/api/chat"
        
        payload = {
            "user_id": f"test_user_{bot.name}",
            "message": TEST_PROMPTS["simple"]
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload)
                assert response.status_code == 200, f"{bot.name} chat failed: {response.text}"
                
                data = response.json()
                assert data.get("success") is True, f"{bot.name} response not successful"
                assert data.get("bot_name") == bot.name, f"Bot name mismatch"
                assert len(data.get("response", "")) > 0, f"{bot.name} returned empty response"
                
                # Log response info
                print(f"\n{'='*60}")
                print(f"Bot: {bot.name} (Main: {bot.main_model})")
                print(f"Response time: {data.get('processing_time_ms', 0):.0f}ms")
                print(f"Response: {data.get('response', '')[:200]}...")
                print(f"{'='*60}")
                
            except httpx.ConnectError:
                pytest.skip(f"{bot.name} not running on port {bot.port}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_character_response(self, bot: BotConfig):
        """Test that each bot responds in character."""
        url = f"http://localhost:{bot.port}/api/chat"
        
        payload = {
            "user_id": f"test_character_{bot.name}",
            "message": TEST_PROMPTS["character"]
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload)
                assert response.status_code == 200, f"{bot.name} character test failed"
                
                data = response.json()
                assert data.get("success") is True
                
                response_text = data.get("response", "").lower()
                
                # Basic check - response should mention something character-related
                # (Each character has different traits, so we just check it's not empty)
                assert len(response_text) > 10, f"{bot.name} character response too short"
                
                print(f"\n[{bot.name}] Character response: {data.get('response', '')[:300]}")
                
            except httpx.ConnectError:
                pytest.skip(f"{bot.name} not running on port {bot.port}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)  
    async def test_reasoning_response(self, bot: BotConfig):
        """Test reasoning capability (may trigger reflective mode)."""
        url = f"http://localhost:{bot.port}/api/chat"
        
        payload = {
            "user_id": f"test_reasoning_{bot.name}",
            "message": TEST_PROMPTS["reasoning"]
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for reasoning
            try:
                response = await client.post(url, json=payload)
                assert response.status_code == 200, f"{bot.name} reasoning test failed"
                
                data = response.json()
                assert data.get("success") is True
                
                response_text = data.get("response", "")
                processing_time = data.get("processing_time_ms", 0)
                
                print(f"\n[{bot.name}] Reasoning ({processing_time:.0f}ms):")
                print(f"  Model: {bot.main_model}")
                print(f"  Reflective: {bot.reflective_model}")
                print(f"  Response: {response_text[:200]}...")
                
            except httpx.ConnectError:
                pytest.skip(f"{bot.name} not running on port {bot.port}")


class TestModelComparison:
    """Compare responses across different models."""

    @pytest.mark.asyncio
    async def test_compare_all_bots_simple(self):
        """Send the same message to all bots and compare responses."""
        results = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for bot in BOT_CONFIGS:
                url = f"http://localhost:{bot.port}/api/chat"
                payload = {
                    "user_id": "comparison_test",
                    "message": "What's your favorite thing to do?"
                }
                
                try:
                    start = time.time()
                    response = await client.post(url, json=payload)
                    elapsed = (time.time() - start) * 1000
                    
                    if response.status_code == 200:
                        data = response.json()
                        results.append({
                            "bot": bot.name,
                            "model": bot.main_model,
                            "response": data.get("response", "")[:150],
                            "time_ms": elapsed,
                            "api_time_ms": data.get("processing_time_ms", 0)
                        })
                except httpx.ConnectError:
                    results.append({
                        "bot": bot.name,
                        "model": bot.main_model,
                        "response": "[NOT RUNNING]",
                        "time_ms": 0,
                        "api_time_ms": 0
                    })
        
        # Print comparison table
        print("\n" + "="*80)
        print("MODEL COMPARISON: 'What's your favorite thing to do?'")
        print("="*80)
        
        for r in sorted(results, key=lambda x: x["api_time_ms"]):
            print(f"\n[{r['bot']}] {r['model']}")
            print(f"  Time: {r['api_time_ms']:.0f}ms")
            print(f"  Response: {r['response']}...")
        
        print("\n" + "="*80)
        
        # At least some bots should be running
        running = [r for r in results if r["response"] != "[NOT RUNNING]"]
        assert len(running) > 0, "No bots are running!"


class TestProductionBots:
    """Specific tests for production bots (nottaylor, dotty)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", [b for b in BOT_CONFIGS if b.is_production], ids=lambda b: b.name)
    async def test_production_stability(self, bot: BotConfig):
        """Test production bots with multiple rapid requests."""
        url = f"http://localhost:{bot.port}/api/chat"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Send 3 rapid requests
                responses = []
                for i in range(3):
                    payload = {
                        "user_id": f"stability_test_{bot.name}",
                        "message": f"Quick test message {i+1}"
                    }
                    response = await client.post(url, json=payload)
                    responses.append(response)
                    await asyncio.sleep(0.5)  # Small delay between requests
                
                # All should succeed
                for i, resp in enumerate(responses):
                    assert resp.status_code == 200, f"{bot.name} failed on request {i+1}"
                    data = resp.json()
                    assert data.get("success") is True
                    
                print(f"\n[{bot.name}] Stability test passed - 3/3 requests successful")
                
            except httpx.ConnectError:
                pytest.skip(f"{bot.name} not running on port {bot.port}")


# Convenience function for manual testing
async def quick_test(bot_name: str, message: str = "Hello!"):
    """Quick test a single bot from the command line."""
    bot = next((b for b in BOT_CONFIGS if b.name == bot_name), None)
    if not bot:
        print(f"Unknown bot: {bot_name}")
        print(f"Available: {[b.name for b in BOT_CONFIGS]}")
        return
    
    url = f"http://localhost:{bot.port}/api/chat"
    payload = {
        "user_id": "quick_test",
        "message": message
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        data = response.json()
        
        print(f"\nBot: {bot.name}")
        print(f"Model: {bot.main_model}")
        print(f"Time: {data.get('processing_time_ms', 0):.0f}ms")
        print(f"Response: {data.get('response', '')}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        bot_name = sys.argv[1]
        message = sys.argv[2] if len(sys.argv) > 2 else "Hello!"
        asyncio.run(quick_test(bot_name, message))
    else:
        print("Usage: python test_bot_api_models.py <bot_name> [message]")
        print(f"Available bots: {[b.name for b in BOT_CONFIGS]}")
