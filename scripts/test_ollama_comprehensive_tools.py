#!/usr/bin/env python3
"""
Comprehensive Ollama Tool Calling Compatibility Test

Tests ALL WhisperEngine tools against a locally running Ollama model,
ensuring full compatibility with the complete tool set (25+ tools across
memory, knowledge, image generation, web search, Discord access, and more).

Usage:
    python scripts/test_ollama_comprehensive_tools.py
    python scripts/test_ollama_comprehensive_tools.py --base-url http://localhost:11434/v1
    python scripts/test_ollama_comprehensive_tools.py --model "llama3.1"
    python scripts/test_ollama_comprehensive_tools.py --langchain  # Test LangChain integration

Requirements:
- Ollama running (usually `ollama serve`)
- Model pulled (e.g., `ollama pull llama3.1`)

Tool-Calling Compatible Models (recommended):
- Llama 3.1 (8b, 70b) - Excellent tool support
- Qwen 2.5 (7b, 14b, 32b) - Best-in-class tool support
- Mistral Nemo - Good support
- Hermes 3 - Good support

Test Coverage:
- Core Memory Tools (search_summaries, search_episodes, lookup_facts)
- Graph & Knowledge Tools (graph_walk, common_ground, lookup_facts)
- Bot Internal Life (search_my_thoughts - diaries, dreams, observations)
- Document Reading (read_document for uploaded files)
- Image Generation (generate_image with style/aspect ratio)
- Web Search & Reading (web_search, read_web_page)
- Discord Tools (search_channels, search_users, get_context)
- Introspection Tools (analyze_patterns, detect_themes)
- Context Tools (planet_context, universe_overview)
- Math Tool (calculator)
- Multi-tool scenarios (complex queries requiring multiple tool calls)
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
# COMPREHENSIVE WHISPERENGINE TOOLS - Full Toolset
# =============================================================================

WHISPERENGINE_COMPREHENSIVE_TOOLS = [
    # ========== MEMORY & SESSION TOOLS ==========
    {
        "type": "function",
        "function": {
            "name": "old_summaries",
            "description": "Search through summarized conversation history. Returns session IDs and summaries of past sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Topic to search for in past sessions"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-10)",
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
            "name": "fetch_session_transcript",
            "description": "Fetch the full transcript of a past session using its session_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to fetch"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max messages to return",
                        "default": 100
                    }
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mem_search",
            "description": "Search through past conversations and memories with a user. Returns episodes with context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memories"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (1-10)",
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
            "name": "graph_memory_search",
            "description": "Search memories using exact text matching in the knowledge graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Exact text or keyword to search"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["query", "user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "full_memory",
            "description": "Fetch the COMPLETE content of a fragmented memory using its message ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID from a search result"
                    }
                },
                "required": ["message_id"]
            }
        }
    },

    # ========== KNOWLEDGE & FACTS ==========
    {
        "type": "function",
        "function": {
            "name": "lookup_user_facts",
            "description": "Look up stored facts about a user from the knowledge graph.",
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
            "name": "update_user_facts",
            "description": "Update or add new facts about a user to the knowledge graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "facts": {
                        "type": "object",
                        "description": "Dict of fact_name -> fact_value to store"
                    }
                },
                "required": ["user_id", "facts"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_preferences",
            "description": "Retrieve user preferences (communication style, interests, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_preferences",
            "description": "Update user preferences and communication style hints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "preferences": {
                        "type": "object",
                        "description": "Dict of preference updates"
                    }
                },
                "required": ["user_id", "preferences"]
            }
        }
    },

    # ========== GRAPH & RELATIONSHIPS ==========
    {
        "type": "function",
        "function": {
            "name": "graph_walk",
            "description": "Walk through the knowledge graph starting from a user/entity, discovering related entities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_entity": {
                        "type": "string",
                        "description": "Entity to start walking from (user ID or name)"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "How deep to walk (1-5)",
                        "default": 2
                    }
                },
                "required": ["start_entity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "common_ground",
            "description": "Find common interests, topics, and shared experiences with a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "char_evolve",
            "description": "Get information about character growth and evolution with a user over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },

    # ========== BOT'S INNER LIFE ==========
    {
        "type": "function",
        "function": {
            "name": "search_my_thoughts",
            "description": "Search through my (the bot's) personal diaries, dreams, observations, and gossip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thought_type": {
                        "type": "string",
                        "enum": ["diary", "dream", "observation", "gossip", "epiphany", "any"],
                        "description": "Type of thought to search",
                        "default": "any"
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional keyword to search for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-5)",
                        "default": 3
                    }
                },
                "required": []
            }
        }
    },

    # ========== DOCUMENTS & FILES ==========
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read the full content of an attached document file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Exact filename including extension (e.g., 'design.md')"
                    }
                },
                "required": ["filename"]
            }
        }
    },

    # ========== IMAGE GENERATION ==========
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image based on a description. Use for creating, drawing, or visualizing ideas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the image to generate"
                    },
                    "image_type": {
                        "type": "string",
                        "enum": ["self", "other", "refine"],
                        "description": "Type of image (self-portrait, other, or refine previous)",
                        "default": "other"
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "enum": ["portrait", "landscape", "square", "widescreen"],
                        "description": "Aspect ratio of the image",
                        "default": "portrait"
                    }
                },
                "required": ["prompt"]
            }
        }
    },

    # ========== WEB TOOLS ==========
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current events, news, and up-to-date information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results (1-10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_web_page",
            "description": "Read and summarize the content of a web page from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the web page to read"
                    }
                },
                "required": ["url"]
            }
        }
    },

    # ========== DISCORD TOOLS ==========
    {
        "type": "function",
        "function": {
            "name": "chan_search",
            "description": "Search for messages in the current Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for channel messages"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (1-20)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "user_search",
            "description": "Search for messages from a specific user in Discord.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_mention": {
                        "type": "string",
                        "description": "@username or user ID"
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional keyword filter"
                    }
                },
                "required": ["user_mention"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "msg_context",
            "description": "Get context around a specific Discord message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID to get context for"
                    },
                    "context_range": {
                        "type": "integer",
                        "description": "Messages before/after to include",
                        "default": 3
                    }
                },
                "required": ["message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recent_msgs",
            "description": "Get recent messages from the current Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent messages (1-50)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },

    # ========== INTROSPECTION & PATTERN ANALYSIS ==========
    {
        "type": "function",
        "function": {
            "name": "conv_patterns",
            "description": "Analyze conversation patterns and communication trends with a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["topics", "sentiment", "frequency", "style"],
                        "description": "Type of pattern analysis"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_themes",
            "description": "Detect recurring themes and topics in conversations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max themes to return (1-10)",
                        "default": 5
                    }
                },
                "required": ["user_id"]
            }
        }
    },

    # ========== CONTEXT & UNIVERSE ==========
    {
        "type": "function",
        "function": {
            "name": "planet_ctx",
            "description": "Get context about the current Discord server/guild.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_members": {
                        "type": "boolean",
                        "description": "Include member list",
                        "default": False
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "universe",
            "description": "Get overview of all servers/channels in the bot's universe.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sibling_info",
            "description": "Get information about other bots in the family.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bot_name": {
                        "type": "string",
                        "description": "Sibling bot name to look up"
                    }
                },
                "required": []
            }
        }
    },

    # ========== MATH & UTILITY ==========
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Perform mathematical calculations and operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2+2', 'sqrt(16)')"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_topic",
            "description": "Perform deep analysis of a topic using combined memory and knowledge tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to analyze"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for user-specific context"
                    }
                },
                "required": ["topic"]
            }
        }
    },
]


# =============================================================================
# COMPREHENSIVE TEST CASES
# =============================================================================

COMPREHENSIVE_TEST_CASES = [
    # Memory & Session Tests
    {"name": "Session History Search", "message": "What did we talk about last week? Can you find a summary of past sessions about my career?", "expected_tool": "old_summaries", "category": "memory"},
    {"name": "Full Session Transcript", "message": "I remember discussing something important in session ABC123. Can you fetch that full conversation?", "expected_tool": "fetch_session_transcript", "category": "memory"},
    {"name": "Episode Memory Search", "message": "Do you remember when we talked about my cat? Can you find those memories?", "expected_tool": "mem_search", "category": "memory"},
    {"name": "Graph Memory Search", "message": "Search for exact mentions of 'anniversary' in our past conversations.", "expected_tool": "graph_memory_search", "category": "memory"},
    {"name": "Full Memory Fragment", "message": "That memory was cut off. Can you get the complete message?", "expected_tool": "full_memory", "category": "memory"},

    # Knowledge & Facts Tests
    {"name": "Fact Lookup", "message": "What do you know about me? My interests, preferences, everything.", "expected_tool": "lookup_user_facts", "category": "knowledge"},
    {"name": "Update Facts", "message": "Remember: I love mountain climbing and I'm a software engineer.", "expected_tool": "update_user_facts", "category": "knowledge"},
    {"name": "User Preferences", "message": "What are my communication preferences? Do I like short or long messages?", "expected_tool": "get_user_preferences", "category": "knowledge"},
    {"name": "Update Preferences", "message": "I prefer brief responses. Use emojis more. Keep things casual.", "expected_tool": "update_user_preferences", "category": "knowledge"},

    # Graph & Relationship Tests
    {"name": "Graph Walk", "message": "Show me my connected relationships. Who do I talk about most? Walk the graph.", "expected_tool": "graph_walk", "category": "graph"},
    {"name": "Common Ground", "message": "What do we have in common? What interests do we share?", "expected_tool": "common_ground", "category": "graph"},
    {"name": "Character Evolution", "message": "How have I changed over time? How has our relationship evolved?", "expected_tool": "char_evolve", "category": "graph"},

    # Bot Inner Life Tests
    {"name": "Search My Thoughts", "message": "What have you been dreaming about? Any interesting observations about me?", "expected_tool": "search_my_thoughts", "category": "inner_life"},

    # Document Tests
    {"name": "Read Document", "message": "I uploaded a file. Can you read DESIGN_SPEC.md and tell me what you think?", "expected_tool": "read_document", "category": "document"},

    # Image Generation Tests
    {"name": "Image Generation", "message": "Can you draw me a picture of a sunset over mountains? Make it cinematic.", "expected_tool": "generate_image", "category": "creative"},
    {"name": "Self Portrait", "message": "Generate an image of yourself. What do you look like?", "expected_tool": "generate_image", "category": "creative"},

    # Web Tools Tests
    {"name": "Web Search", "message": "What's the latest news about AI? Search the web for me.", "expected_tool": "web_search", "category": "web"},
    {"name": "Read Web Page", "message": "Can you read this article? https://example.com/article and summarize it?", "expected_tool": "read_web_page", "category": "web"},

    # Discord Tools Tests
    {"name": "Channel Search", "message": "Search the channel for discussions about Python.", "expected_tool": "chan_search", "category": "discord"},
    {"name": "User Search", "message": "What has @alice been saying? Search her messages.", "expected_tool": "user_search", "category": "discord"},
    {"name": "Message Context", "message": "What was the context around message 123456789? Show me surrounding messages.", "expected_tool": "msg_context", "category": "discord"},
    {"name": "Recent Messages", "message": "What's been happening recently in this channel?", "expected_tool": "recent_msgs", "category": "discord"},

    # Introspection Tests
    {"name": "Conversation Patterns", "message": "What patterns do you notice in how I communicate? Analyze my conversation style.", "expected_tool": "conv_patterns", "category": "introspection"},
    {"name": "Theme Detection", "message": "What are the recurring themes in our conversations? What topics do I keep coming back to?", "expected_tool": "find_themes", "category": "introspection"},

    # Context Tests
    {"name": "Planet Context", "message": "Tell me about this server. Who's here? What's it about?", "expected_tool": "planet_ctx", "category": "context"},
    {"name": "Universe Overview", "message": "What servers are you in? Give me an overview of your universe.", "expected_tool": "universe", "category": "context"},
    {"name": "Sibling Info", "message": "Tell me about your bot siblings. What are the other bots like?", "expected_tool": "sibling_info", "category": "context"},

    # Utility Tests
    {"name": "Calculator", "message": "What's 42 * 12? Can you do some math?", "expected_tool": "calculator", "category": "utility"},
    {"name": "Topic Analysis", "message": "Analyze the topic of artificial intelligence. What do you know about it from our conversations?", "expected_tool": "analyze_topic", "category": "utility"},

    # Complex Multi-Tool Tests
    {"name": "Complex Query (Memory + Analysis)", "message": "Look back at our past conversations, find mentions of machine learning, and analyze the patterns of when I talk about tech.", "expected_tool": "mem_search", "category": "complex"},
    {"name": "Complex Query (Facts + Web)", "message": "What are my known interests, and can you search the web for trending topics related to those interests?", "expected_tool": "lookup_user_facts", "category": "complex"},
    {"name": "Complex Query (Image + Document)", "message": "Read this document and then generate an image based on what you learn from it.", "expected_tool": "read_document", "category": "complex"},
]


# =============================================================================
# TEST RUNNER
# =============================================================================

class OllamaToolTester:
    def __init__(self, base_url: str, model: Optional[str] = None):
        self.base_url = base_url
        self.model = model
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="not-needed"
        )
        self.results = []
        self._detected_model = None
        self.category_results = {}

    async def get_model_info(self) -> dict:
        """Fetch loaded model info from Ollama."""
        try:
            models = await self.client.models.list()
            if models.data:
                model_info = models.data[0]
                self._detected_model = model_info.id
                return {
                    "id": model_info.id,
                    "created": model_info.created,
                    "owned_by": model_info.owned_by,
                }
        except Exception as e:
            print(f"Warning: Could not fetch model info: {e}")
        return {}

    async def test_tool_calling(self, test_case: dict) -> dict:
        """Test if model can invoke the expected tool correctly."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model or self._detected_model or "llama2",
                messages=[
                    {
                        "role": "user",
                        "content": test_case["message"]
                    }
                ],
                tools=WHISPERENGINE_COMPREHENSIVE_TOOLS,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=500
            )

            # Check if tool was called
            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                expected = test_case.get("expected_tool")
                
                if tool_call.function.name == expected:
                    status = "PASS"
                else:
                    status = "PARTIAL"
                
                return {
                    "name": test_case["name"],
                    "category": test_case.get("category", "unknown"),
                    "status": status,
                    "tool_called": tool_call.function.name,
                    "expected_tool": expected,
                    "args": tool_call.function.arguments,
                    "error": None,
                }
            else:
                return {
                    "name": test_case["name"],
                    "category": test_case.get("category", "unknown"),
                    "status": "FAIL",
                    "tool_called": None,
                    "expected_tool": test_case.get("expected_tool"),
                    "args": None,
                    "error": None,
                }

        except Exception as e:
            return {
                "name": test_case["name"],
                "category": test_case.get("category", "unknown"),
                "status": "ERROR",
                "error": str(e),
                "expected_tool": test_case.get("expected_tool"),
                "tool_called": None,
                "args": None,
            }

    async def run_all_tests(self) -> None:
        """Run all comprehensive tests."""
        print("=" * 80)
        print("🧪 COMPREHENSIVE OLLAMA TOOL CALLING TEST")
        print("=" * 80)
        
        model_info = await self.get_model_info()
        print(f"\n📡 Endpoint: {self.base_url}")
        print(f"🤖 Model: {self.model or model_info.get('id', 'Unknown')}")
        print(f"📚 Testing {len(COMPREHENSIVE_TEST_CASES)} test cases across {len(WHISPERENGINE_COMPREHENSIVE_TOOLS)} tools\n")
        
        print("─" * 80)
        print("Running tests...\n")
        
        for test_case in COMPREHENSIVE_TEST_CASES:
            result = await self.test_tool_calling(test_case)
            self.results.append(result)
            
            status_symbol = "✅" if result["status"] == "PASS" else ("⚠️" if result["status"] == "PARTIAL" else "❌")
            print(f"  {status_symbol} {result['name']}")
            
            category = result["category"]
            if category not in self.category_results:
                self.category_results[category] = {"passed": 0, "partial": 0, "failed": 0, "error": 0}
            
            if result["status"] == "PASS":
                self.category_results[category]["passed"] += 1
            elif result["status"] == "PARTIAL":
                self.category_results[category]["partial"] += 1
            elif result["status"] == "ERROR":
                self.category_results[category]["error"] += 1
            else:
                self.category_results[category]["failed"] += 1
        
        self.print_results()

    def print_results(self) -> None:
        """Print comprehensive test results."""
        print("\n" + "─" * 80)
        print("📊 RESULTS SUMMARY BY CATEGORY")
        print("─" * 80 + "\n")
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        
        print(f"  ✅ Passed:  {passed}/{len(self.results)}")
        print(f"  ⚠️ Partial: {partial}/{len(self.results)}")
        print(f"  ❌ Failed:  {failed}/{len(self.results)}")
        print(f"  💥 Errors:  {errors}/{len(self.results)}\n")
        
        print("Category Breakdown:")
        for category in sorted(self.category_results.keys()):
            stats = self.category_results[category]
            total = stats["passed"] + stats["partial"] + stats["failed"] + stats["error"]
            print(f"  {category.upper():15} - Passed: {stats['passed']}/{total} | "
                  f"Partial: {stats['partial']} | Failed: {stats['failed']} | Error: {stats['error']}")
        
        print("\n" + "─" * 80)
        print("📝 DETAILED RESULTS")
        print("─" * 80 + "\n")
        
        for result in self.results:
            print(f"[{result['status']}] {result['name']}")
            if result["status"] != "PASS":
                if result["tool_called"]:
                    print(f"  Expected: {result['expected_tool']}, Got: {result['tool_called']}")
                else:
                    print(f"  Expected: {result['expected_tool']}, Got: No tool called")
            if "error" in result and result["error"]:
                print(f"  Error: {result['error']}")
            print()
        
        print("=" * 80)
        if failed == 0 and errors == 0 and partial <= 2:
            print("🎉 VERDICT: FULLY COMPATIBLE (or minimal issues)")
            print("   This model is ready for WhisperEngine production use!")
        elif failed <= 3 and errors <= 2:
            print("✅ VERDICT: MOSTLY COMPATIBLE")
            print("   This model works well but may have issues with specific tool types.")
        else:
            print("⚠️ VERDICT: PARTIAL COMPATIBILITY")
            print("   This model has compatibility issues that need attention.")
        print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive Ollama tool calling compatibility test for WhisperEngine"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434/v1",
        help="Base URL of Ollama API (default: http://localhost:11434/v1)"
    )
    parser.add_argument(
        "--model",
        help="Specific model to test (optional, auto-detects if not specified)"
    )
    parser.add_argument(
        "--langchain",
        action="store_true",
        help="Test LangChain bind_tools() integration (future feature)"
    )
    
    args = parser.parse_args()
    
    tester = OllamaToolTester(
        base_url=args.base_url,
        model=args.model
    )
    
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
