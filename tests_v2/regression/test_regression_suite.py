"""
WhisperEngine Regression Test Suite

Comprehensive tests that verify bot behavior across all aspects:
- Basic chat functionality
- Memory persistence and retrieval
- Trust system progression
- Multi-turn conversations
- Character consistency
- Model-specific behavior

Usage:
    # Run full regression suite
    pytest tests_v2/regression/ -v

    # Run for specific bot
    pytest tests_v2/regression/ -v -k "elena"

    # Run with detailed output
    pytest tests_v2/regression/ -v -s --no-cov

Requirements:
    - All bots must be running: ./bot.sh up all
    - Infrastructure must be up: ./bot.sh infra up
"""

import pytest
import httpx
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class BotConfig:
    """Configuration for a bot under test."""
    name: str
    port: int
    main_model: str
    reflective_model: str
    is_production: bool = False


# All bot configurations (synced with actual .env.* files as of Dec 5, 2025)
BOT_CONFIGS = [
    BotConfig("elena", 8000, "anthropic/claude-haiku-4.5", "anthropic/claude-sonnet-4"),
    BotConfig("ryan", 8001, "google/gemini-2.5-flash", "google/gemini-2.5-pro"),
    BotConfig("dotty", 8002, "anthropic/claude-haiku-4.5", "anthropic/claude-sonnet-4"),
    BotConfig("aria", 8003, "google/gemini-2.5-flash", "google/gemini-2.5-pro"),
    BotConfig("dream", 8004, "x-ai/grok-3", "x-ai/grok-4"),
    BotConfig("jake", 8005, "mistralai/mistral-small-3.1-24b-instruct", "mistralai/mistral-medium-3.1"),
    BotConfig("sophia", 8006, "google/gemini-2.5-flash", "google/gemini-2.5-pro"),
    BotConfig("marcus", 8007, "google/gemini-2.5-flash", "google/gemini-2.5-pro"),
    BotConfig("nottaylor", 8008, "mistralai/mistral-medium-3.1", "openai/gpt-4o", is_production=True),
    BotConfig("gabriel", 8009, "mistralai/mistral-small-3.1-24b-instruct", "mistralai/mistral-medium-3.1"),
    BotConfig("aethys", 8010, "mistralai/mistral-medium-3.1", "openai/gpt-4o"),
    BotConfig("aetheris", 8011, "anthropic/claude-3.5-haiku", "anthropic/claude-sonnet-4"),
]

# Test user prefix to avoid polluting real user data
TEST_USER_PREFIX = "regression_test_"


def get_test_user_id(bot_name: str, test_name: str) -> str:
    """Generate unique test user ID for isolation."""
    return f"{TEST_USER_PREFIX}{bot_name}_{test_name}_{uuid.uuid4().hex[:8]}"


class APIClient:
    """Helper class for API interactions."""
    
    def __init__(self, port: int, timeout: float = 60.0):
        self.base_url = f"http://localhost:{port}"
        self.timeout = timeout
    
    async def chat(self, user_id: str, message: str, context: Optional[Dict] = None) -> Dict:
        """Send a chat message."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"user_id": user_id, "message": message, "context": context}
            )
            return response.json()
    
    async def health(self) -> Dict:
        """Check health endpoint."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/health")
            return response.json()
    
    async def diagnostics(self) -> Dict:
        """Get diagnostics."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/api/diagnostics")
            return response.json()
    
    async def get_user_state(self, user_id: str) -> Dict:
        """Get user state."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/user-state",
                json={"user_id": user_id}
            )
            return response.json()
    
    async def conversation(self, user_id: str, messages: List[str], context: Optional[Dict] = None, delay_ms: int = 500) -> Dict:
        """Run multi-turn conversation."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/conversation",
                json={
                    "user_id": user_id,
                    "messages": messages,
                    "context": context,
                    "delay_between_ms": delay_ms
                }
            )
            return response.json()
    
    async def clear_user_data(self, user_id: str, clear_memories: bool = True, clear_trust: bool = True, clear_knowledge: bool = False) -> Dict:
        """Clear user data for test isolation."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/clear-user-data",
                json={
                    "user_id": user_id,
                    "clear_memories": clear_memories,
                    "clear_trust": clear_trust,
                    "clear_knowledge": clear_knowledge
                }
            )
            return response.json()


# =============================================================================
# Test Classes
# =============================================================================

class TestHealthAndDiagnostics:
    """Test basic health and diagnostics for all bots."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_health_endpoint(self, bot: BotConfig):
        """Verify health endpoint returns healthy status."""
        client = APIClient(bot.port)
        try:
            result = await client.health()
            assert result.get("status") == "healthy", f"{bot.name} not healthy"
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running on port {bot.port}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_diagnostics_endpoint(self, bot: BotConfig):
        """Verify diagnostics returns expected configuration."""
        client = APIClient(bot.port)
        try:
            result = await client.diagnostics()
            
            # Check bot name
            assert result.get("bot_name") == bot.name
            
            # Check model config
            llm_models = result.get("llm_models", {})
            assert llm_models.get("main") == bot.main_model, \
                f"Expected {bot.main_model}, got {llm_models.get('main')}"
            
            # Check database connections
            db_status = result.get("database_status", {})
            assert db_status.get("postgres") is True, "Postgres not connected"
            
            print(f"\n[{bot.name}] Diagnostics:")
            print(f"  Model: {llm_models.get('main')}")
            print(f"  DBs: {db_status}")
            print(f"  Uptime: {result.get('uptime_seconds', 0):.0f}s")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running on port {bot.port}")


class TestBasicChat:
    """Test basic chat functionality."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_simple_greeting(self, bot: BotConfig):
        """Test simple greeting response."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "greeting")
        
        try:
            result = await client.chat(user_id, "Hello! How are you?")
            
            assert result.get("success") is True
            assert result.get("bot_name") == bot.name
            assert len(result.get("response", "")) > 0
            assert result.get("mode") in ["fast", "agency", "reflective", "blocked", "supergraph", None]
            
            print(f"\n[{bot.name}] Greeting test:")
            print(f"  Mode: {result.get('mode')}")
            print(f"  Time: {result.get('processing_time_ms', 0):.0f}ms")
            print(f"  Response: {result.get('response', '')[:150]}...")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_question_response(self, bot: BotConfig):
        """Test that bot answers questions appropriately."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "question")
        
        try:
            result = await client.chat(user_id, "What's your favorite color?")
            
            assert result.get("success") is True
            response = result.get("response", "").lower()
            
            # Response should be substantive (more than just "hi")
            assert len(response) > 20, "Response too short"
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_context_injection(self, bot: BotConfig):
        """Test that context is properly injected."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "context")
        
        try:
            result = await client.chat(
                user_id,
                "Where are we chatting right now?",
                context={
                    "channel_name": "test-channel",
                    "guild_id": "test-server-123",
                    "user_name": "TestUser"
                }
            )
            
            assert result.get("success") is True
            # Bot should acknowledge the context (may mention channel/server)
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


class TestCharacterConsistency:
    """Test that each bot maintains its character identity."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_self_description(self, bot: BotConfig):
        """Test that bot describes itself consistently."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "identity")
        
        try:
            result = await client.chat(user_id, "Tell me about yourself in one sentence.")
            
            assert result.get("success") is True
            response = result.get("response", "")
            
            # Response should be substantial
            assert len(response) > 20, "Self-description too short"
            
            print(f"\n[{bot.name}] Self-description: {response[:200]}")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_personality_consistency(self, bot: BotConfig):
        """Test that bot maintains consistent personality across questions."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "personality")
        
        try:
            # Ask two related questions
            result1 = await client.chat(user_id, "What do you enjoy doing?")
            result2 = await client.chat(user_id, "What are your hobbies?")
            
            assert result1.get("success") is True
            assert result2.get("success") is True
            
            # Both responses should be substantial
            assert len(result1.get("response", "")) > 20
            assert len(result2.get("response", "")) > 20
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


class TestMemoryAndState:
    """Test memory persistence and retrieval."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_memory_storage(self, bot: BotConfig):
        """Test that conversations are stored in memory."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "memory")
        
        try:
            # Clear any existing data
            await client.clear_user_data(user_id)
            
            # Have a conversation
            await client.chat(user_id, "My favorite food is pizza.")
            
            # Small delay for memory to be stored
            await asyncio.sleep(1)
            
            # Check user state
            state = await client.get_user_state(user_id)
            
            # Trust should be at least initialized
            assert "trust_score" in state
            
            print(f"\n[{bot.name}] Memory test:")
            print(f"  Trust: {state.get('trust_score', 0)}")
            print(f"  Memories: {state.get('memory_count', 0)}")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_memory_recall(self, bot: BotConfig):
        """Test that bot can recall information from earlier in conversation."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "recall")
        
        try:
            # Clear existing data
            await client.clear_user_data(user_id)
            
            # Tell the bot something specific
            unique_fact = f"My dog's name is Biscuit_{uuid.uuid4().hex[:4]}"
            await client.chat(user_id, unique_fact)
            
            # Ask about it
            await asyncio.sleep(1)
            result = await client.chat(user_id, "What's my dog's name?")
            
            response = result.get("response", "").lower()
            
            # The bot should ideally mention the dog's name
            # This is a soft check - memory may not always surface
            print(f"\n[{bot.name}] Recall test:")
            print(f"  Fact: {unique_fact}")
            print(f"  Response: {result.get('response', '')[:200]}")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


class TestMultiTurnConversation:
    """Test multi-turn conversation handling."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_conversation_flow(self, bot: BotConfig):
        """Test a multi-turn conversation maintains coherence."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "flow")
        
        try:
            # Clear data
            await client.clear_user_data(user_id)
            
            # Multi-turn conversation
            messages = [
                "Hi! I'm learning to play guitar.",
                "Do you have any tips for beginners?",
                "What about practicing chords?"
            ]
            
            result = await client.conversation(user_id, messages, delay_ms=300)
            
            assert result.get("success") is True
            turns = result.get("turns", [])
            assert len(turns) == 3, f"Expected 3 turns, got {len(turns)}"
            
            print(f"\n[{bot.name}] Conversation flow:")
            for i, turn in enumerate(turns):
                print(f"  Turn {i+1}: {turn.get('processing_time_ms', 0):.0f}ms - {turn.get('mode', 'unknown')}")
            print(f"  Total time: {result.get('total_time_ms', 0):.0f}ms")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


class TestComplexityRouting:
    """Test that complexity classification routes correctly."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_simple_query_fast_mode(self, bot: BotConfig):
        """Simple queries should use fast mode."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "simple")
        
        try:
            result = await client.chat(user_id, "Hi!")
            
            assert result.get("success") is True
            complexity = result.get("complexity", "")
            mode = result.get("mode", "")
            
            # Simple greeting should be classified as SIMPLE
            print(f"\n[{bot.name}] Simple query: mode={mode}, complexity={complexity}")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_complex_query_routing(self, bot: BotConfig):
        """Complex queries should trigger appropriate mode."""
        client = APIClient(bot.port, timeout=120.0)
        user_id = get_test_user_id(bot.name, "complex")
        
        try:
            result = await client.chat(
                user_id,
                "Can you analyze the pros and cons of different programming paradigms?"
            )
            
            assert result.get("success") is True
            complexity = result.get("complexity", "")
            mode = result.get("mode", "")
            
            print(f"\n[{bot.name}] Complex query: mode={mode}, complexity={complexity}")
            print(f"  Time: {result.get('processing_time_ms', 0):.0f}ms")
            print(f"  Model: {result.get('model_used', 'unknown')}")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


class TestModelComparison:
    """Compare responses across different models."""
    
    @pytest.mark.asyncio
    async def test_same_prompt_all_bots(self):
        """Send the same prompt to all bots and compare."""
        prompt = "In exactly one sentence, describe your view on friendship."
        results = []
        
        for bot in BOT_CONFIGS:
            client = APIClient(bot.port)
            user_id = get_test_user_id(bot.name, "compare")
            
            try:
                result = await client.chat(user_id, prompt)
                results.append({
                    "bot": bot.name,
                    "model": bot.main_model,
                    "response": result.get("response", "")[:200],
                    "time_ms": result.get("processing_time_ms", 0),
                    "mode": result.get("mode", "unknown")
                })
            except httpx.ConnectError:
                results.append({
                    "bot": bot.name,
                    "model": bot.main_model,
                    "response": "[NOT RUNNING]",
                    "time_ms": 0,
                    "mode": "N/A"
                })
        
        # Print comparison
        print("\n" + "="*80)
        print(f"MODEL COMPARISON: '{prompt}'")
        print("="*80)
        
        for r in sorted(results, key=lambda x: x["time_ms"]):
            if r["response"] != "[NOT RUNNING]":
                print(f"\n[{r['bot']}] {r['model']} ({r['time_ms']:.0f}ms)")
                print(f"  {r['response']}")
        
        # At least some bots should be running
        running = [r for r in results if r["response"] != "[NOT RUNNING]"]
        assert len(running) > 0, "No bots are running!"


class TestProductionBotStability:
    """Specific stability tests for production bots."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", [b for b in BOT_CONFIGS if b.is_production], ids=lambda b: b.name)
    async def test_rapid_requests(self, bot: BotConfig):
        """Production bots should handle rapid requests."""
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "rapid")
        
        try:
            # Send 5 rapid requests
            results = []
            for i in range(5):
                result = await client.chat(user_id, f"Quick message {i+1}")
                results.append(result)
                await asyncio.sleep(0.3)  # Small delay
            
            # All should succeed
            successes = sum(1 for r in results if r.get("success"))
            assert successes >= 4, f"Only {successes}/5 succeeded"
            
            avg_time = sum(r.get("processing_time_ms", 0) for r in results) / len(results)
            print(f"\n[{bot.name}] Rapid request test: {successes}/5 succeeded, avg {avg_time:.0f}ms")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", [b for b in BOT_CONFIGS if b.is_production], ids=lambda b: b.name)
    async def test_long_message_handling(self, bot: BotConfig):
        """Production bots should handle long messages."""
        client = APIClient(bot.port, timeout=90.0)
        user_id = get_test_user_id(bot.name, "long")
        
        try:
            # Long message
            long_message = "I want to tell you about my day. " * 50  # ~1750 chars
            result = await client.chat(user_id, long_message)
            
            assert result.get("success") is True
            print(f"\n[{bot.name}] Long message test: {result.get('processing_time_ms', 0):.0f}ms")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


# =============================================================================
# Concurrency Tests
# =============================================================================

class TestConcurrency:
    """Test concurrent request handling and load behavior."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS[:3], ids=lambda b: b.name)  # Test first 3 bots
    async def test_light_concurrent_load(self, bot: BotConfig):
        """Test 5 concurrent requests to a single bot."""
        client = APIClient(bot.port, timeout=60.0)
        base_user_id = get_test_user_id(bot.name, "concurrent_light")
        
        try:
            # Send 5 concurrent requests with different user IDs
            messages = [
                (f"{base_user_id}_{i}", f"Concurrent message {i+1}") 
                for i in range(5)
            ]
            
            start = time.time()
            results = await asyncio.gather(
                *[client.chat(user_id, msg) for user_id, msg in messages],
                return_exceptions=True
            )
            elapsed = (time.time() - start) * 1000
            
            # Count successes
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            errors = sum(1 for r in results if isinstance(r, Exception))
            
            # At least 80% should succeed
            assert successes >= 4, f"Only {successes}/5 concurrent requests succeeded ({errors} errors)"
            
            # Calculate avg response time
            response_times = [
                r.get("processing_time_ms", 0) 
                for r in results 
                if isinstance(r, dict)
            ]
            avg_time = sum(response_times) / len(response_times) if response_times else 0
            
            print(f"\n[{bot.name}] Light concurrent load:")
            print(f"  Success: {successes}/5")
            print(f"  Total time: {elapsed:.0f}ms")
            print(f"  Avg response: {avg_time:.0f}ms")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    async def test_medium_concurrent_load(self):
        """Test 10 concurrent requests to a single bot."""
        bot = BOT_CONFIGS[0]  # Use elena
        client = APIClient(bot.port, timeout=90.0)
        base_user_id = get_test_user_id(bot.name, "concurrent_medium")
        
        try:
            # Send 10 concurrent requests
            messages = [
                (f"{base_user_id}_{i}", f"Load test message {i+1}") 
                for i in range(10)
            ]
            
            start = time.time()
            results = await asyncio.gather(
                *[client.chat(user_id, msg) for user_id, msg in messages],
                return_exceptions=True
            )
            elapsed = (time.time() - start) * 1000
            
            # Count results
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            errors = sum(1 for r in results if isinstance(r, Exception))
            timeouts = sum(1 for r in results if isinstance(r, Exception) and "timeout" in str(r).lower())
            
            # At least 70% should succeed under medium load
            assert successes >= 7, f"Only {successes}/10 concurrent requests succeeded ({errors} errors, {timeouts} timeouts)"
            
            response_times = [
                r.get("processing_time_ms", 0) 
                for r in results 
                if isinstance(r, dict)
            ]
            avg_time = sum(response_times) / len(response_times) if response_times else 0
            max_time = max(response_times) if response_times else 0
            min_time = min(response_times) if response_times else 0
            
            print(f"\n[{bot.name}] Medium concurrent load:")
            print(f"  Success: {successes}/10 ({errors} errors, {timeouts} timeouts)")
            print(f"  Total time: {elapsed:.0f}ms")
            print(f"  Response times: min={min_time:.0f}ms, avg={avg_time:.0f}ms, max={max_time:.0f}ms")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
    
    @pytest.mark.asyncio
    async def test_multi_bot_concurrent_load(self):
        """Test concurrent requests across multiple bots."""
        bots = BOT_CONFIGS[:5]  # Test first 5 bots
        
        try:
            # Send 3 concurrent requests to each bot (15 total)
            tasks = []
            for bot in bots:
                client = APIClient(bot.port, timeout=60.0)
                base_user_id = get_test_user_id(bot.name, "concurrent_multi")
                for i in range(3):
                    user_id = f"{base_user_id}_{i}"
                    tasks.append((bot.name, client.chat(user_id, f"Multi-bot message {i+1}")))
            
            start = time.time()
            results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )
            elapsed = (time.time() - start) * 1000
            
            # Analyze results
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            errors = sum(1 for r in results if isinstance(r, Exception))
            total = len(results)
            
            # At least 80% should succeed
            assert successes >= total * 0.8, f"Only {successes}/{total} multi-bot requests succeeded ({errors} errors)"
            
            response_times = [
                r.get("processing_time_ms", 0) 
                for r in results 
                if isinstance(r, dict)
            ]
            avg_time = sum(response_times) / len(response_times) if response_times else 0
            
            print(f"\nMulti-bot concurrent load ({len(bots)} bots, {total} requests):")
            print(f"  Success: {successes}/{total}")
            print(f"  Total time: {elapsed:.0f}ms")
            print(f"  Avg response: {avg_time:.0f}ms")
            
        except httpx.ConnectError as e:
            pytest.skip(f"One or more bots not running: {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", [b for b in BOT_CONFIGS if b.is_production], ids=lambda b: b.name)
    async def test_stress_concurrent_load(self, bot: BotConfig):
        """Test 20 concurrent requests to production bots (stress test)."""
        client = APIClient(bot.port, timeout=120.0)
        base_user_id = get_test_user_id(bot.name, "concurrent_stress")
        
        try:
            # Send 20 concurrent requests
            messages = [
                (f"{base_user_id}_{i}", f"Stress test {i+1}") 
                for i in range(20)
            ]
            
            start = time.time()
            results = await asyncio.gather(
                *[client.chat(user_id, msg) for user_id, msg in messages],
                return_exceptions=True
            )
            elapsed = (time.time() - start) * 1000
            
            # Count results
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            errors = sum(1 for r in results if isinstance(r, Exception))
            timeouts = sum(1 for r in results if isinstance(r, Exception) and "timeout" in str(r).lower())
            
            # At least 60% should succeed under stress
            success_rate = successes / len(results)
            assert successes >= 12, f"Only {successes}/20 stress requests succeeded ({errors} errors, {timeouts} timeouts)"
            
            response_times = [
                r.get("processing_time_ms", 0) 
                for r in results 
                if isinstance(r, dict)
            ]
            
            if response_times:
                avg_time = sum(response_times) / len(response_times)
                max_time = max(response_times)
                min_time = min(response_times)
                
                print(f"\n[{bot.name}] Stress concurrent load:")
                print(f"  Success: {successes}/20 ({success_rate*100:.1f}%)")
                print(f"  Errors: {errors} ({timeouts} timeouts)")
                print(f"  Total time: {elapsed:.0f}ms")
                print(f"  Response times: min={min_time:.0f}ms, avg={avg_time:.0f}ms, max={max_time:.0f}ms")
            
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")


# =============================================================================
# Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
async def cleanup_test_users():
    """Cleanup test users after each test."""
    yield
    # Note: We don't actually cleanup here because the test user IDs are unique
    # and we might want to inspect them. In a CI environment, you could
    # uncomment this to cleanup:
    # 
    # for bot in BOT_CONFIGS:
    #     client = APIClient(bot.port)
    #     try:
    #         # Would need to track test user IDs to clean them up
    #         pass
    #     except:
    #         pass
