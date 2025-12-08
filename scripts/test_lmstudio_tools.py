#!/usr/bin/env python3
"""
Test LM Studio Tool Calling Compatibility

Tests whether a locally running LM Studio model supports the OpenAI-compatible
tool/function calling format required by WhisperEngine.

Usage:
    python scripts/test_lmstudio_tools.py
    python scripts/test_lmstudio_tools.py --base-url http://localhost:1234/v1
    python scripts/test_lmstudio_tools.py --model "qwen2.5-7b-instruct"
    python scripts/test_lmstudio_tools.py --langchain  # Test LangChain bind_tools()

Requirements:
- LM Studio running with a model loaded
- Model should support tool calling (Qwen2.5, Llama 3.1+, Mistral Nemo, etc.)

Tool-Calling Compatible Models (recommended):
- Qwen2.5-Instruct (any size) - BEST tool support
- Llama 3.1/3.2/3.3-Instruct
- Mistral Nemo / Ministral-Instruct
- Hermes 3 / Firefunction v2

Output:
- ✅ PASS: Model correctly calls tools with proper arguments
- ⚠️ PARTIAL: Model calls tools but with issues (wrong format, missing args)
- ❌ FAIL: Model doesn't support tool calling or returns raw text
"""

import asyncio
import argparse
import json
import sys
from typing import Optional, Type, List
from datetime import datetime

try:
    from openai import AsyncOpenAI
except ImportError:
    print("❌ Missing dependency: pip install openai")
    sys.exit(1)

# LangChain imports (optional, for --langchain mode)
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.tools import BaseTool
    from langchain_core.messages import HumanMessage, AIMessage
    from pydantic import BaseModel, Field
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


# =============================================================================
# TEST TOOLS - Simulating WhisperEngine's tool definitions
# =============================================================================

WHISPERENGINE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": "Search through past conversations and memories with a user. Use this when the user asks 'do you remember' or references past events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memories (e.g., 'our conversation about cats')"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID to search memories for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to return (1-10)",
                        "default": 5
                    }
                },
                "required": ["query", "user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_facts",
            "description": "Retrieve known facts about a user from the knowledge graph. Use this to recall what you know about someone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "fact_type": {
                        "type": "string",
                        "enum": ["preferences", "relationships", "interests", "all"],
                        "description": "Type of facts to retrieve",
                        "default": "all"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image based on a description. Use when the user asks you to create, draw, or generate an image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the image to generate"
                    },
                    "style": {
                        "type": "string",
                        "enum": ["realistic", "anime", "artistic", "sketch"],
                        "description": "Art style for the image",
                        "default": "realistic"
                    }
                },
                "required": ["prompt"]
            }
        }
    }
]


# =============================================================================
# TEST CASES
# =============================================================================

TEST_CASES = [
    {
        "name": "Memory Recall",
        "message": "Do you remember when we talked about my cat Luna last week?",
        "expected_tool": "search_memories",
        "expected_args": ["query", "user_id"],
        "description": "Tests if model can invoke memory search with proper arguments"
    },
    {
        "name": "Fact Lookup",
        "message": "What do you know about me?",
        "expected_tool": "get_user_facts",
        "expected_args": ["user_id"],
        "description": "Tests if model retrieves user facts from knowledge graph"
    },
    {
        "name": "Image Generation",
        "message": "Can you draw me a picture of a sunset over mountains?",
        "expected_tool": "generate_image",
        "expected_args": ["prompt"],
        "description": "Tests if model triggers image generation with descriptive prompt"
    },
    {
        "name": "No Tool Needed",
        "message": "Hello! How are you today?",
        "expected_tool": None,
        "expected_args": [],
        "description": "Tests if model responds normally without unnecessary tool calls"
    },
    {
        "name": "Complex Query (Multiple Potential Tools)",
        "message": "What did we discuss about my job, and can you make an image of my workplace?",
        "expected_tool": "search_memories",  # Should prioritize one, ideally memories first
        "expected_args": ["query"],
        "description": "Tests handling of queries that could use multiple tools"
    }
]


# =============================================================================
# TEST RUNNER
# =============================================================================

class LMStudioToolTester:
    def __init__(self, base_url: str, model: Optional[str] = None):
        self.base_url = base_url
        self.model = model
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="lm-studio"  # LM Studio ignores this but requires it
        )
        self.results = []
        self._detected_model = None  # Cache detected model

    async def get_model_info(self) -> dict:
        """Fetch loaded model info from LM Studio."""
        try:
            models = await self.client.models.list()
            if models.data:
                model_info = models.data[0]
                self._detected_model = model_info.id  # Cache for later use
                return {
                    "id": model_info.id,
                    "owned_by": getattr(model_info, "owned_by", "unknown"),
                    "available": True
                }
            return {"id": "unknown", "available": False}
        except Exception as e:
            return {"id": "error", "error": str(e), "available": False}

    def _get_model_name(self) -> str:
        """Get model name to use for API calls."""
        return self.model or self._detected_model or "local-model"

    async def test_tool_calling(self, test_case: dict) -> dict:
        """Run a single tool calling test."""
        result = {
            "name": test_case["name"],
            "message": test_case["message"],
            "expected_tool": test_case["expected_tool"],
            "status": "unknown",
            "details": {}
        }

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant with access to tools. Use tools when appropriate to answer user queries. Always include the user_id 'test_user_123' when calling tools that require it."
                },
                {
                    "role": "user",
                    "content": test_case["message"]
                }
            ]

            # Make the API call with tools
            response = await self.client.chat.completions.create(
                model=self._get_model_name(),
                messages=messages,
                tools=WHISPERENGINE_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=500
            )

            choice = response.choices[0]
            result["details"]["finish_reason"] = choice.finish_reason
            result["details"]["raw_content"] = choice.message.content

            # Check if tool was called
            if choice.message.tool_calls:
                tool_call = choice.message.tool_calls[0]
                result["details"]["tool_called"] = tool_call.function.name
                result["details"]["tool_id"] = tool_call.id
                
                # Parse arguments
                try:
                    args = json.loads(tool_call.function.arguments)
                    result["details"]["tool_args"] = args
                except json.JSONDecodeError:
                    result["details"]["tool_args_raw"] = tool_call.function.arguments
                    result["details"]["parse_error"] = True

                # Validate result
                if test_case["expected_tool"] is None:
                    # Expected no tool, but got one
                    result["status"] = "warning"
                    result["details"]["note"] = "Tool called when none expected (not necessarily wrong)"
                elif tool_call.function.name == test_case["expected_tool"]:
                    # Correct tool called
                    args = result["details"].get("tool_args", {})
                    missing_args = [a for a in test_case["expected_args"] if a not in args]
                    
                    if missing_args:
                        result["status"] = "partial"
                        result["details"]["missing_args"] = missing_args
                    else:
                        result["status"] = "pass"
                else:
                    result["status"] = "wrong_tool"
                    result["details"]["note"] = f"Expected {test_case['expected_tool']}, got {tool_call.function.name}"
            else:
                # No tool called
                if test_case["expected_tool"] is None:
                    result["status"] = "pass"
                    result["details"]["note"] = "Correctly responded without tools"
                else:
                    result["status"] = "fail"
                    result["details"]["note"] = f"Expected {test_case['expected_tool']} but no tool called"

        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
            result["details"]["error_type"] = type(e).__name__

        return result

    async def run_all_tests(self) -> dict:
        """Run all test cases and return summary."""
        print("\n" + "="*70)
        print("🧪 LM STUDIO TOOL CALLING COMPATIBILITY TEST")
        print("="*70)

        # Get model info
        model_info = await self.get_model_info()
        print(f"\n📡 Endpoint: {self.base_url}")
        print(f"🤖 Model: {model_info.get('id', 'unknown')}")
        
        if not model_info.get("available"):
            print(f"\n❌ ERROR: Cannot connect to LM Studio")
            print(f"   {model_info.get('error', 'No model loaded')}")
            print("\n💡 Make sure LM Studio is running with a model loaded")
            return {"success": False, "error": model_info.get("error")}

        print(f"\n{'─'*70}")
        print("Running tests...\n")

        results = []
        for test in TEST_CASES:
            print(f"  Testing: {test['name']}...", end=" ", flush=True)
            result = await self.test_tool_calling(test)
            results.append(result)
            
            status_icon = {
                "pass": "✅",
                "partial": "⚠️",
                "warning": "⚡",
                "wrong_tool": "🔀",
                "fail": "❌",
                "error": "💥"
            }.get(result["status"], "❓")
            
            print(f"{status_icon} {result['status'].upper()}")

        # Summary
        print(f"\n{'─'*70}")
        print("📊 RESULTS SUMMARY")
        print(f"{'─'*70}\n")

        passed = sum(1 for r in results if r["status"] == "pass")
        partial = sum(1 for r in results if r["status"] in ["partial", "warning"])
        failed = sum(1 for r in results if r["status"] in ["fail", "wrong_tool", "error"])

        print(f"  ✅ Passed:  {passed}/{len(results)}")
        print(f"  ⚠️ Partial: {partial}/{len(results)}")
        print(f"  ❌ Failed:  {failed}/{len(results)}")

        # Detailed results
        print(f"\n{'─'*70}")
        print("📝 DETAILED RESULTS")
        print(f"{'─'*70}")

        for result in results:
            print(f"\n[{result['status'].upper()}] {result['name']}")
            print(f"  Query: \"{result['message'][:50]}...\"" if len(result['message']) > 50 else f"  Query: \"{result['message']}\"")
            
            if result["details"].get("tool_called"):
                print(f"  Tool: {result['details']['tool_called']}")
                if result["details"].get("tool_args"):
                    args_str = json.dumps(result["details"]["tool_args"], indent=None)
                    if len(args_str) > 60:
                        args_str = args_str[:60] + "..."
                    print(f"  Args: {args_str}")
            
            if result["details"].get("note"):
                print(f"  Note: {result['details']['note']}")
            
            if result["details"].get("error"):
                print(f"  Error: {result['details']['error']}")

        # Compatibility verdict
        print(f"\n{'='*70}")
        if passed == len(results):
            print("🎉 VERDICT: FULLY COMPATIBLE")
            print("   This model works great with WhisperEngine tool calling!")
            compatible = True
        elif passed + partial >= len(results) * 0.6:
            print("⚡ VERDICT: MOSTLY COMPATIBLE")
            print("   This model should work but may have occasional issues.")
            compatible = True
        elif passed > 0:
            print("⚠️ VERDICT: PARTIALLY COMPATIBLE")
            print("   This model has limited tool support. Consider a different model.")
            compatible = False
        else:
            print("❌ VERDICT: NOT COMPATIBLE")
            print("   This model does not support the required tool calling format.")
            print("\n💡 Recommended models with good tool support:")
            print("   - Qwen2.5-Instruct (any size)")
            print("   - Llama 3.1/3.2/3.3-Instruct")
            print("   - Mistral Nemo / Ministral-Instruct")
            print("   - Hermes 3 / Firefunction v2")
            compatible = False
        print("="*70 + "\n")

        return {
            "success": True,
            "compatible": compatible,
            "model": model_info.get("id"),
            "passed": passed,
            "partial": partial,
            "failed": failed,
            "total": len(results),
            "results": results
        }


async def test_parallel_tool_calls(base_url: str, model: Optional[str] = None) -> dict:
    """Test if model supports parallel tool calling (advanced feature)."""
    print("\n" + "─"*70)
    print("🔄 BONUS: Testing Parallel Tool Calls")
    print("─"*70)
    
    client = AsyncOpenAI(base_url=base_url, api_key="lm-studio")
    
    # Auto-detect model if not specified
    if not model:
        try:
            models = await client.models.list()
            if models.data:
                model = models.data[0].id
        except Exception:
            model = "local-model"
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI assistant. When appropriate, you can call multiple tools in parallel."
                },
                {
                    "role": "user",
                    "content": "What do you remember about my cats, and also what facts do you know about me?"
                }
            ],
            tools=WHISPERENGINE_TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500
        )
        
        choice = response.choices[0]
        if choice.message.tool_calls and len(choice.message.tool_calls) > 1:
            print(f"  ✅ Supports parallel tool calls ({len(choice.message.tool_calls)} tools called)")
            for tc in choice.message.tool_calls:
                print(f"     - {tc.function.name}")
            return {"parallel_tools": True, "count": len(choice.message.tool_calls)}
        elif choice.message.tool_calls:
            print(f"  ⚡ Single tool called (parallel not triggered)")
            print(f"     - {choice.message.tool_calls[0].function.name}")
            return {"parallel_tools": False, "count": 1}
        else:
            print(f"  ❌ No tools called")
            return {"parallel_tools": False, "count": 0}
            
    except Exception as e:
        print(f"  💥 Error: {e}")
        return {"parallel_tools": False, "error": str(e)}


async def test_stress_with_context(base_url: str, model: Optional[str] = None, context_size: int = 4000) -> dict:
    """
    Stress test: Can the model still call tools correctly with a large context?
    
    This simulates real WhisperEngine conditions where the model receives:
    - System prompt (~500 tokens)
    - Character context (~500 tokens)
    - Recent memories (~2000 tokens)
    - Chat history (~2000 tokens)
    - User message
    
    Many local models pass basic tests but fail under load.
    """
    print("\n" + "="*70)
    print("🏋️ STRESS TEST: Tool Calling Under Load")
    print("="*70)
    print(f"\n📊 Injecting ~{context_size} tokens of context before tool call...")
    
    client = AsyncOpenAI(base_url=base_url, api_key="lm-studio")
    
    # Auto-detect model if not specified
    if not model:
        try:
            models = await client.models.list()
            if models.data:
                model = models.data[0].id
        except Exception:
            model = "local-model"
    
    print(f"🤖 Model: {model}")
    
    # Generate dummy context (~4 chars per token estimate)
    chars_needed = context_size * 4
    
    # Simulate realistic context sections
    memory_block = """
[MEMORY CONTEXT]
Memory 1 (2 days ago): User mentioned they have a cat named Luna who likes to sit on their keyboard.
Memory 2 (1 week ago): User shared they work as a software engineer at a startup.
Memory 3 (2 weeks ago): User expressed interest in learning more about AI and machine learning.
Memory 4 (3 weeks ago): User mentioned they enjoy hiking on weekends.
Memory 5 (1 month ago): User talked about their favorite coffee shop downtown.
""" * (chars_needed // 500 // 5 + 1)  # Repeat to fill
    
    knowledge_block = """
[KNOWLEDGE GRAPH FACTS]
- User works in technology sector
- User has pet: cat (Luna)
- User hobby: hiking
- User interest: AI/ML
- User preference: coffee
- User location: urban area
""" * (chars_needed // 500 // 6 + 1)
    
    chat_history = """
[RECENT CONVERSATION]
User: Hey, how's it going?
Assistant: I'm doing well! How are you today?
User: Pretty good, just got back from a hike.
Assistant: That sounds refreshing! Where did you go hiking?
User: The usual trail by the lake. Luna was upset I left her alone.
Assistant: Cats do get lonely! Did she give you the cold shoulder when you got back?
""" * (chars_needed // 500 // 6 + 1)
    
    # Trim to approximate target size
    total_context = (memory_block + knowledge_block + chat_history)[:chars_needed]
    
    results = {
        "context_tokens_approx": context_size,
        "tests": []
    }
    
    stress_tests = [
        {
            "name": "Memory Search (with context)",
            "message": "Do you remember what we discussed about my job last month?",
            "expected_tool": "search_memories"
        },
        {
            "name": "Fact Lookup (with context)",
            "message": "What are my hobbies again?",
            "expected_tool": "get_user_facts"
        },
        {
            "name": "No Tool Needed (with context)",
            "message": "Thanks for chatting with me!",
            "expected_tool": None
        }
    ]
    
    print(f"\n{'─'*70}")
    print("Running stress tests...\n")
    
    for test in stress_tests:
        print(f"  Testing: {test['name']}...", end=" ", flush=True)
        
        test_result = {
            "name": test["name"],
            "expected_tool": test["expected_tool"],
            "status": "unknown"
        }
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a helpful AI assistant with access to tools.
Use tools when appropriate to answer user queries.
Always include the user_id 'test_user_123' when calling tools that require it.

{total_context}
"""
                    },
                    {
                        "role": "user",
                        "content": test["message"]
                    }
                ],
                tools=WHISPERENGINE_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=500
            )
            
            choice = response.choices[0]
            
            if choice.message.tool_calls:
                tool_call = choice.message.tool_calls[0]
                tool_name = tool_call.function.name
                
                test_result["tool_called"] = tool_name
                
                if test["expected_tool"] is None:
                    test_result["status"] = "warning"
                    print("⚡ WARNING (tool called when not expected)")
                elif tool_name == test["expected_tool"]:
                    test_result["status"] = "pass"
                    print("✅ PASS")
                else:
                    test_result["status"] = "wrong_tool"
                    print(f"🔀 WRONG ({tool_name})")
            else:
                if test["expected_tool"] is None:
                    test_result["status"] = "pass"
                    print("✅ PASS")
                else:
                    test_result["status"] = "fail"
                    print(f"❌ FAIL (no tool called)")
                    
        except Exception as e:
            test_result["status"] = "error"
            test_result["error"] = str(e)
            print(f"💥 ERROR: {str(e)[:40]}")
        
        results["tests"].append(test_result)
    
    # Summary
    passed = sum(1 for t in results["tests"] if t["status"] == "pass")
    total = len(results["tests"])
    
    print(f"\n{'─'*70}")
    print("📊 STRESS TEST RESULTS")
    print(f"{'─'*70}")
    print(f"\n  Tests Passed: {passed}/{total}")
    print(f"  Context Size: ~{context_size} tokens")
    
    print(f"\n{'='*70}")
    if passed == total:
        print("🎉 STRESS TEST VERDICT: PASSED")
        print("   Model handles tool calling under realistic context load!")
        results["compatible"] = True
    elif passed > 0:
        print("⚡ STRESS TEST VERDICT: PARTIAL")
        print("   Model struggles with some tool calls under load.")
        results["compatible"] = False
    else:
        print("❌ STRESS TEST VERDICT: FAILED")
        print("   Model cannot reliably call tools with large context.")
        print("   Consider using a larger model or reducing context size.")
        results["compatible"] = False
    print("="*70)
    
    return results


# =============================================================================
# LANGCHAIN NATIVE TOOL CALLING TEST
# =============================================================================

# Define LangChain tools that mirror WhisperEngine's actual tool patterns
if LANGCHAIN_AVAILABLE:
    
    class SearchMemoriesInput(BaseModel):
        """Input for searching memories."""
        query: str = Field(description="What to search for in memories")
        user_id: str = Field(description="The user's ID to search memories for")
        limit: int = Field(default=5, description="Maximum number of memories to return (1-10)")

    class SearchMemoriesTool(BaseTool):
        """Search through past conversations and memories with a user."""
        name: str = "mem_search"  # Short name for local model compatibility
        description: str = "Search through past conversations and memories. Use when the user asks 'do you remember' or references past events."
        args_schema: Type[BaseModel] = SearchMemoriesInput
        
        def _run(self, query: str, user_id: str, limit: int = 5) -> str:
            return f"[MOCK] Found {limit} memories matching '{query}' for user {user_id}"
        
        async def _arun(self, query: str, user_id: str, limit: int = 5) -> str:
            return self._run(query, user_id, limit)

    class GetUserFactsInput(BaseModel):
        """Input for getting user facts."""
        user_id: str = Field(description="The user's ID")
        fact_type: str = Field(default="all", description="Type of facts: preferences, relationships, interests, all")

    class GetUserFactsTool(BaseTool):
        """Retrieve known facts about a user from the knowledge graph."""
        name: str = "user_facts"  # Short name for local model compatibility
        description: str = "Retrieve known facts about a user. Use to recall what you know about someone."
        args_schema: Type[BaseModel] = GetUserFactsInput
        
        def _run(self, user_id: str, fact_type: str = "all") -> str:
            return f"[MOCK] Retrieved {fact_type} facts for user {user_id}"
        
        async def _arun(self, user_id: str, fact_type: str = "all") -> str:
            return self._run(user_id, fact_type)

    class GenerateImageInput(BaseModel):
        """Input for image generation."""
        prompt: str = Field(description="Detailed description of the image to generate")
        style: str = Field(default="realistic", description="Art style: realistic, anime, artistic, sketch")

    class GenerateImageTool(BaseTool):
        """Generate an image based on a description."""
        name: str = "gen_image"  # Short name for local model compatibility
        description: str = "Generate an image based on a description. Use when user asks to create, draw, or generate an image."
        args_schema: Type[BaseModel] = GenerateImageInput
        
        def _run(self, prompt: str, style: str = "realistic") -> str:
            return f"[MOCK] Generated {style} image: {prompt[:50]}..."
        
        async def _arun(self, prompt: str, style: str = "realistic") -> str:
            return self._run(prompt, style)

    LANGCHAIN_TOOLS = [
        SearchMemoriesTool(),
        GetUserFactsTool(),
        GenerateImageTool()
    ]


async def test_langchain_tools(base_url: str, model: Optional[str] = None) -> dict:
    """
    Test LangChain's native bind_tools() with LM Studio.
    
    This tests the EXACT pattern WhisperEngine uses in its agent workflows.
    """
    if not LANGCHAIN_AVAILABLE:
        print("\n❌ LangChain not available. Install with: pip install langchain-openai")
        return {"success": False, "error": "LangChain not installed"}
    
    print("\n" + "="*70)
    print("🔗 LANGCHAIN bind_tools() COMPATIBILITY TEST")
    print("="*70)
    print("\nThis tests the EXACT pattern WhisperEngine uses in agent workflows.")
    print(f"📡 Endpoint: {base_url}")
    
    results = {
        "success": True,
        "tests": []
    }
    
    try:
        # Auto-detect model if not specified
        if not model:
            try:
                from openai import OpenAI
                client = OpenAI(base_url=base_url, api_key="lm-studio")
                models = client.models.list()
                if models.data:
                    model = models.data[0].id
                    print(f"🤖 Model: {model}")
                else:
                    model = "local-model"
            except Exception:
                model = "local-model"
        else:
            print(f"🤖 Model: {model}")
        
        # Create LLM exactly like WhisperEngine does
        llm = ChatOpenAI(
            api_key="lm-studio",
            base_url=base_url,
            model=model,
            temperature=0.7,
            timeout=180  # Updated from request_timeout (deprecated)
        )
        
        # Bind tools - this is the critical operation
        llm_with_tools = llm.bind_tools(LANGCHAIN_TOOLS)
        
        print(f"\n{'─'*70}")
        print("Running LangChain tool binding tests...\n")
        
        # Test cases - using SHORT tool names for local model compatibility
        langchain_tests = [
            {
                "name": "Memory Search (bind_tools)",
                "message": "Do you remember our conversation about my dog Max?",
                "expected_tool": "mem_search"
            },
            {
                "name": "Fact Retrieval (bind_tools)",
                "message": "What facts do you know about me?",
                "expected_tool": "user_facts"
            },
            {
                "name": "Image Generation (bind_tools)",
                "message": "Please create an image of a dragon flying over a castle",
                "expected_tool": "gen_image"
            },
            {
                "name": "No Tool Needed (bind_tools)",
                "message": "Hi there! What's your name?",
                "expected_tool": None
            }
        ]
        
        for test in langchain_tests:
            print(f"  Testing: {test['name']}...", end=" ", flush=True)
            
            test_result = {
                "name": test["name"],
                "expected_tool": test["expected_tool"],
                "status": "unknown"
            }
            
            try:
                # Invoke with tools bound
                messages = [
                    HumanMessage(content=f"[Context: User ID is test_user_123]\n\n{test['message']}")
                ]
                
                response = await llm_with_tools.ainvoke(messages)
                
                # Check for tool calls in response
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    tool_call = response.tool_calls[0]
                    tool_name = tool_call.get('name', tool_call.get('function', {}).get('name', 'unknown'))
                    tool_args = tool_call.get('args', {})
                    
                    test_result["tool_called"] = tool_name
                    test_result["tool_args"] = tool_args
                    
                    if test["expected_tool"] is None:
                        test_result["status"] = "warning"
                        print("⚡ WARNING (tool called when not expected)")
                    elif tool_name == test["expected_tool"]:
                        test_result["status"] = "pass"
                        print("✅ PASS")
                    elif test["expected_tool"].startswith(tool_name) or tool_name.startswith(test["expected_tool"]):
                        # Handle truncated tool names (e.g., search_mem vs search_memories)
                        test_result["status"] = "partial"
                        test_result["note"] = f"Tool name truncated: '{tool_name}' (expected '{test['expected_tool']}')"
                        print(f"⚠️ PARTIAL (truncated name: {tool_name})")
                    else:
                        test_result["status"] = "wrong_tool"
                        print(f"🔀 WRONG TOOL (expected {test['expected_tool']}, got {tool_name})")
                else:
                    # No tool calls
                    if test["expected_tool"] is None:
                        test_result["status"] = "pass"
                        test_result["response"] = response.content[:100] if response.content else ""
                        print("✅ PASS (responded without tools)")
                    else:
                        test_result["status"] = "fail"
                        test_result["response"] = response.content[:100] if response.content else ""
                        print(f"❌ FAIL (no tool called, expected {test['expected_tool']})")
                        
            except Exception as e:
                test_result["status"] = "error"
                test_result["error"] = str(e)
                print(f"💥 ERROR: {str(e)[:50]}")
            
            results["tests"].append(test_result)
        
        # Test tool execution loop (agent pattern)
        print(f"\n{'─'*70}")
        print("🔄 Testing Agent Loop Pattern (invoke → tool_call → tool_result → final)")
        print("─"*70)
        
        try:
            # Step 1: Initial invocation with tools
            messages = [
                HumanMessage(content="[User ID: test_user_123]\n\nDo you remember what we talked about yesterday?")
            ]
            response = await llm_with_tools.ainvoke(messages)
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print(f"  Step 1: Tool requested ✅")
                tool_call = response.tool_calls[0]
                tool_name = tool_call.get('name', 'unknown')
                tool_args = tool_call.get('args', {})
                tool_id = tool_call.get('id', 'call_123')
                print(f"          → {tool_name}({json.dumps(tool_args)[:60]}...)")
                
                # Step 2: Execute tool and return result
                from langchain_core.messages import ToolMessage
                
                mock_result = f"Found 3 memories from yesterday: discussed weather, talked about hobbies, shared a joke"
                
                messages.append(response)  # Add AI message with tool call
                messages.append(ToolMessage(
                    content=mock_result,
                    tool_call_id=tool_id
                ))
                
                print(f"  Step 2: Tool executed ✅")
                print(f"          → Result: {mock_result[:50]}...")
                
                # Step 3: Get final response
                final_response = await llm_with_tools.ainvoke(messages)
                
                if final_response.content and not (hasattr(final_response, 'tool_calls') and final_response.tool_calls):
                    print(f"  Step 3: Final response ✅")
                    print(f"          → \"{final_response.content[:80]}...\"")
                    results["agent_loop"] = {
                        "status": "pass",
                        "final_response": final_response.content[:200]
                    }
                else:
                    print(f"  Step 3: ⚠️ Model made another tool call instead of responding")
                    results["agent_loop"] = {
                        "status": "partial",
                        "note": "Model made additional tool call"
                    }
            else:
                print(f"  ❌ Model didn't call any tools")
                results["agent_loop"] = {"status": "fail", "note": "No initial tool call"}
                
        except Exception as e:
            print(f"  💥 Agent loop error: {e}")
            results["agent_loop"] = {"status": "error", "error": str(e)}
        
        # Summary
        print(f"\n{'─'*70}")
        print("📊 LANGCHAIN RESULTS SUMMARY")
        print(f"{'─'*70}")
        
        passed = sum(1 for t in results["tests"] if t["status"] == "pass")
        partial = sum(1 for t in results["tests"] if t["status"] in ["partial", "warning"])
        failed = sum(1 for t in results["tests"] if t["status"] in ["fail", "wrong_tool", "error"])
        
        print(f"\n  Tool Binding Tests:")
        print(f"    ✅ Passed:  {passed}/{len(results['tests'])}")
        print(f"    ⚠️ Partial: {partial}/{len(results['tests'])}")
        print(f"    ❌ Failed:  {failed}/{len(results['tests'])}")
        
        agent_status = results.get("agent_loop", {}).get("status", "unknown")
        print(f"\n  Agent Loop Pattern: {agent_status.upper()}")
        
        # Verdict
        print(f"\n{'='*70}")
        if passed == len(results["tests"]) and agent_status == "pass":
            print("🎉 LANGCHAIN VERDICT: FULLY COMPATIBLE")
            print("   This model works with WhisperEngine's LangChain agent workflows!")
            results["compatible"] = True
        elif passed >= len(results["tests"]) * 0.5 and agent_status in ["pass", "partial"]:
            print("⚡ LANGCHAIN VERDICT: MOSTLY COMPATIBLE")
            print("   This model should work but may have occasional issues.")
            results["compatible"] = True
        else:
            print("❌ LANGCHAIN VERDICT: NOT COMPATIBLE")
            print("   This model does not support LangChain's bind_tools() properly.")
            results["compatible"] = False
        print("="*70)
        
    except Exception as e:
        print(f"\n💥 Critical error: {e}")
        results["success"] = False
        results["error"] = str(e)
        results["compatible"] = False
    
    return results


async def list_available_models(base_url: str) -> List[str]:
    """List all models available at the endpoint."""
    try:
        client = AsyncOpenAI(base_url=base_url, api_key="lm-studio")
        models = await client.models.list()
        return [m.id for m in models.data] if models.data else []
    except Exception as e:
        print(f"❌ Error listing models: {e}")
        return []


async def test_all_models(base_url: str, test_langchain: bool = True) -> dict:
    """Test all available models at the endpoint."""
    models = await list_available_models(base_url)
    
    if not models:
        print("❌ No models found at endpoint")
        return {"success": False, "error": "No models found"}
    
    print("\n" + "="*70)
    print("🔄 TESTING ALL AVAILABLE MODELS")
    print("="*70)
    print(f"\nFound {len(models)} model(s) at {base_url}:")
    for m in models:
        print(f"  • {m}")
    
    results = {}
    
    for i, model in enumerate(models, 1):
        print(f"\n{'─'*70}")
        print(f"[{i}/{len(models)}] Testing: {model}")
        print("─"*70)
        
        model_result = {
            "model": model,
            "openai_api": None,
            "langchain": None,
            "compatible": False
        }
        
        # Run OpenAI API test
        tester = LMStudioToolTester(base_url, model)
        openai_result = await tester.run_all_tests()
        model_result["openai_api"] = {
            "passed": openai_result.get("passed", 0),
            "total": openai_result.get("total", 0),
            "compatible": openai_result.get("compatible", False)
        }
        
        # Run LangChain test
        if test_langchain:
            langchain_result = await test_langchain_tools(base_url, model)
            model_result["langchain"] = {
                "passed": sum(1 for t in langchain_result.get("tests", []) if t.get("status") == "pass"),
                "total": len(langchain_result.get("tests", [])),
                "agent_loop": langchain_result.get("agent_loop", {}).get("status", "unknown"),
                "compatible": langchain_result.get("compatible", False)
            }
        
        # Overall compatibility
        openai_ok = model_result["openai_api"].get("compatible", False)
        langchain_ok = model_result.get("langchain", {}).get("compatible", True)
        model_result["compatible"] = openai_ok and langchain_ok
        
        results[model] = model_result
    
    # Summary
    print("\n" + "="*70)
    print("📊 ALL MODELS SUMMARY")
    print("="*70 + "\n")
    
    compatible_models = [m for m, r in results.items() if r["compatible"]]
    partial_models = [m for m, r in results.items() if not r["compatible"] and (
        r["openai_api"].get("passed", 0) > 0 or 
        r.get("langchain", {}).get("passed", 0) > 0
    )]
    incompatible_models = [m for m, r in results.items() if not r["compatible"] and m not in partial_models]
    
    print(f"{'Model':<40} {'OpenAI API':<15} {'LangChain':<15} {'Status':<10}")
    print("─"*80)
    
    for model, result in results.items():
        openai_str = f"{result['openai_api']['passed']}/{result['openai_api']['total']}"
        if result.get("langchain"):
            lc_str = f"{result['langchain']['passed']}/{result['langchain']['total']}"
        else:
            lc_str = "N/A"
        
        if result["compatible"]:
            status = "✅ PASS"
        elif model in partial_models:
            status = "⚠️ PARTIAL"
        else:
            status = "❌ FAIL"
        
        print(f"{model:<40} {openai_str:<15} {lc_str:<15} {status:<10}")
    
    print("\n" + "─"*80)
    print(f"\n✅ Fully Compatible: {len(compatible_models)}")
    for m in compatible_models:
        print(f"   • {m}")
    
    if partial_models:
        print(f"\n⚠️ Partially Compatible: {len(partial_models)}")
        for m in partial_models:
            print(f"   • {m}")
    
    if incompatible_models:
        print(f"\n❌ Not Compatible: {len(incompatible_models)}")
        for m in incompatible_models:
            print(f"   • {m}")
    
    print()
    
    return {
        "success": True,
        "models_tested": len(models),
        "compatible": compatible_models,
        "partial": partial_models,
        "incompatible": incompatible_models,
        "details": results
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Test LM Studio tool calling compatibility for WhisperEngine"
    )
    parser.add_argument(
        "--endpoint", "--base-url",
        dest="base_url",
        default="http://localhost:1234/v1",
        help="LM Studio API endpoint URL (default: http://localhost:1234/v1)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name to use (default: auto-detect loaded model)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Also test parallel tool calling support"
    )
    parser.add_argument(
        "--langchain",
        action="store_true",
        help="Test LangChain bind_tools() compatibility (recommended)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests (OpenAI API + parallel + LangChain)"
    )
    parser.add_argument(
        "--all-models",
        action="store_true",
        help="Test ALL models available at the /models endpoint"
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Just list available models without testing"
    )
    parser.add_argument(
        "--stress",
        action="store_true",
        help="Run stress test with ~4k tokens of context"
    )
    parser.add_argument(
        "--stress-tokens",
        type=int,
        default=4000,
        help="Number of tokens for stress test (default: 4000)"
    )
    
    args = parser.parse_args()
    
    # List models only
    if args.list_models:
        models = await list_available_models(args.base_url)
        if models:
            print(f"Available models at {args.base_url}:")
            for m in models:
                print(f"  • {m}")
        else:
            print("No models found")
        sys.exit(0)
    
    # Test all models
    if args.all_models:
        results = await test_all_models(args.base_url, test_langchain=True)
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        # Exit based on whether any models are compatible
        sys.exit(0 if results.get("compatible") else 1)
    
    # If --all, enable everything
    if args.all:
        args.parallel = True
        args.langchain = True
        args.stress = True
    
    all_results = {}
    
    # Run OpenAI API tests (unless only langchain requested)
    if not args.langchain or args.all:
        tester = LMStudioToolTester(args.base_url, args.model)
        results = await tester.run_all_tests()
        all_results["openai_api"] = results
        
        if args.parallel and results.get("success"):
            parallel_result = await test_parallel_tool_calls(args.base_url, args.model)
            all_results["parallel_tools"] = parallel_result
    
    # Run LangChain tests
    if args.langchain or args.all:
        langchain_results = await test_langchain_tools(args.base_url, args.model)
        all_results["langchain"] = langchain_results
    
    # Run stress test
    if args.stress:
        stress_results = await test_stress_with_context(
            args.base_url, args.model, args.stress_tokens
        )
        all_results["stress_test"] = stress_results
    
    if args.json:
        print(json.dumps(all_results, indent=2, default=str))
    
    # Overall compatibility
    openai_ok = all_results.get("openai_api", {}).get("compatible", True)
    langchain_ok = all_results.get("langchain", {}).get("compatible", True)
    stress_ok = all_results.get("stress_test", {}).get("compatible", True)
    
    sys.exit(0 if (openai_ok and langchain_ok and stress_ok) else 1)


if __name__ == "__main__":
    asyncio.run(main())
