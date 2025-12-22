#!/usr/bin/env python3
"""
Comprehensive LLM API Tool Calling Compatibility Test

Tests ALL WhisperEngine tools against any OpenAI-compatible LLM API endpoint,
ensuring full compatibility with the complete tool set (29 tools across
memory, knowledge, image generation, web search, Discord access, and more).

Works with any OpenAI-compatible endpoint:
- LM Studio (local)
- vLLM (local or remote)
- Ollama (local)
- OpenRouter, Anthropic, OpenAI (cloud)
- Any other OpenAI API-compatible service

Usage:
    # Test local LM Studio (native function calling)
    python scripts/test_comprehensive_llm_tools.py
    
    # Test any OpenAI-compatible endpoint
    python scripts/test_comprehensive_llm_tools.py --base-url http://localhost:1234/v1
    python scripts/test_comprehensive_llm_tools.py --base-url http://gx10.local:8000/v1
    python scripts/test_comprehensive_llm_tools.py --base-url https://api.openrouter.io/v1
    
    # Specify model
    python scripts/test_comprehensive_llm_tools.py --model "qwen2.5-7b-instruct"
    python scripts/test_comprehensive_llm_tools.py --model "gpt-4"
    
    # Test LangChain integration (WhisperEngine production pattern)
    python scripts/test_comprehensive_llm_tools.py --langchain
    python scripts/test_comprehensive_llm_tools.py --base-url http://gx10.local:8000/v1 --langchain

Test Coverage (29 tools):
- Memory Tools (old_summaries, mem_search, full_memory, fetch_session_transcript, graph_memory_search)
- Knowledge Tools (lookup_user_facts, update_user_facts, get_prefs, save_prefs)
- Graph Tools (graph_walk, common_ground, char_evolve)
- Bot Inner Life (search_my_thoughts - diaries, dreams, observations)
- Document Tools (read_document)
- Image Generation (generate_image)
- Web Tools (web_search, read_web_page)
- Discord Tools (chan_search, user_search, msg_context, recent_msgs)
- Introspection Tools (conv_patterns, find_themes)
- Context Tools (planet_ctx, universe, sibling_info)
- Utility Tools (calculator, check_goals)
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
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from pydantic import BaseModel, Field
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


# =============================================================================
# LANGCHAIN TOOL DEFINITIONS (for --langchain mode)
# =============================================================================

if LANGCHAIN_AVAILABLE:
    # Create simplified LangChain tools for testing bind_tools()
    class SearchMemoriesInput(BaseModel):
        query: str = Field(description="What to search for in memories")
        user_id: str = Field(description="The user's ID")
        limit: int = Field(default=5, description="Max results (1-10)")

    class SearchMemoriesTool(BaseTool):
        name: str = "mem_search"
        description: str = "Search through past conversations and memories. Use when user asks 'do you remember' or references past events."
        args_schema: Type[BaseModel] = SearchMemoriesInput
        
        def _run(self, query: str, user_id: str, limit: int = 5) -> str:
            return f"[MOCK] Found {limit} memories matching '{query}'"
        
        async def _arun(self, query: str, user_id: str, limit: int = 5) -> str:
            return self._run(query, user_id, limit)

    class LookupFactsInput(BaseModel):
        query: str = Field(description="Natural language query for user facts")

    class LookupFactsTool(BaseTool):
        name: str = "lookup_user_facts"
        description: str = "Retrieve facts about a user from the knowledge graph."
        args_schema: Type[BaseModel] = LookupFactsInput
        
        def _run(self, query: str) -> str:
            return f"[MOCK] Found facts related to: {query}"
        
        async def _arun(self, query: str) -> str:
            return self._run(query)

    class GenerateImageInput(BaseModel):
        prompt: str = Field(description="Description of image to generate")
        aspect_ratio: str = Field(default="portrait", description="Aspect ratio")

    class GenerateImageTool(BaseTool):
        name: str = "generate_image"
        description: str = "Generate an image. Use when user asks to create, draw, or generate an image."
        args_schema: Type[BaseModel] = GenerateImageInput
        
        def _run(self, prompt: str, aspect_ratio: str = "portrait") -> str:
            return f"[MOCK] Generated {aspect_ratio} image: {prompt[:50]}"
        
        async def _arun(self, prompt: str, aspect_ratio: str = "portrait") -> str:
            return self._run(prompt, aspect_ratio)

    LANGCHAIN_TOOLS = [
        SearchMemoriesTool(),
        LookupFactsTool(),
        GenerateImageTool()
    ]


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
            "description": "Search for memories using exact text matching in the knowledge graph. Use when looking for specific words, phrases, or when semantic search fails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Exact text or keyword to search for in memory content"
                    }
                },
                "required": ["query"]
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
            "description": "Updates or deletes facts in the Knowledge Graph based on user correction. Use when user explicitly says something has changed or was wrong.",
            "parameters": {
                "type": "object",
                "properties": {
                    "correction": {
                        "type": "string",
                        "description": "The user's correction or update (e.g., 'I moved to Seattle', 'I don't like pizza anymore')"
                    }
                },
                "required": ["correction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_prefs",
            "description": "Retrieve user's saved preferences (communication style, settings, etc.).",
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
            "name": "save_prefs",
            "description": "Update user preferences and communication style hints (e.g., 'be concise', 'use emojis').",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["update", "delete"],
                        "description": "Whether to update or delete a preference"
                    },
                    "key": {
                        "type": "string",
                        "description": "Preference key (e.g., 'verbosity', 'style')"
                    },
                    "value": {
                        "type": "string",
                        "description": "New value (for update action)"
                    }
                },
                "required": ["action", "key"]
            }
        }
    },

    # ========== GRAPH & RELATIONSHIPS ==========
    {
        "type": "function",
        "function": {
            "name": "graph_walk",
            "description": "Explores the knowledge graph to find hidden connections, thematic clusters, and relationships. Use when user asks 'what is connected?', 'explore the graph', 'find connections'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_node": {
                        "type": "string",
                        "description": "Starting point: 'user' (default), 'character', or specific entity name",
                        "default": "user"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "How many hops to explore (1-3). Default is 2.",
                        "default": 2
                    }
                },
                "required": []
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
            "description": "Analyzes conversation patterns including topics, emotional trends, and engagement styles over a time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lookback_hours": {
                        "type": "integer",
                        "description": "How many hours of conversation history to analyze (default: 24)",
                        "default": 24
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_themes",
            "description": "Identifies recurring themes in conversations. Searches for patterns in user's conversation history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What themes to search for (e.g., 'work', 'hobbies', 'family')",
                        "default": "themes topics interests hobbies"
                    }
                },
                "required": []
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

    # ========== GOALS & UTILITY ==========
    {
        "type": "function",
        "function": {
            "name": "check_goals",
            "description": "Check what goals are currently active for this user.",
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
]


# =============================================================================
# COMPREHENSIVE TEST CASES
# =============================================================================

COMPREHENSIVE_TEST_CASES = [
    # Memory & Session Tests
    {
        "name": "Session History Search",
        "message": "What did we talk about last week? Can you find a summary of past sessions about my career?",
        "expected_tool": "old_summaries",
        "category": "memory"
    },
    {
        "name": "Full Session Transcript",
        "message": "I remember discussing something important in session ABC123. Can you fetch that full conversation?",
        "expected_tool": "fetch_session_transcript",
        "category": "memory"
    },
    {
        "name": "Episode Memory Search",
        "message": "Do you remember when we talked about my cat? Can you find those memories?",
        "expected_tool": "mem_search",
        "category": "memory"
    },
    {
        "name": "Graph Memory Search",
        "message": "I need exact keyword matching - search the graph for the word 'anniversary' in our conversations.",
        "expected_tool": "graph_memory_search",
        "category": "memory"
    },
    {
        "name": "Full Memory Fragment",
        "message": "That memory result was truncated. Can you fetch the full memory for message ID msg_12345?",
        "expected_tool": "full_memory",
        "category": "memory"
    },

    # Knowledge & Facts Tests
    {
        "name": "Fact Lookup",
        "message": "What do you know about me? My interests, preferences, everything.",
        "expected_tool": "lookup_user_facts",
        "category": "knowledge"
    },
    {
        "name": "Update Facts",
        "message": "Actually, I need to correct something: I'm not a software engineer anymore, I switched careers to data science.",
        "expected_tool": "update_user_facts",
        "category": "knowledge"
    },
    {
        "name": "User Preferences",
        "message": "What are my saved preferences? What communication style settings do I have?",
        "expected_tool": "get_prefs",
        "category": "knowledge"
    },
    {
        "name": "Update Preferences",
        "message": "Save my preference: I prefer brief responses. Use emojis more. Keep things casual.",
        "expected_tool": "save_prefs",
        "category": "knowledge"
    },

    # Graph & Relationship Tests
    {
        "name": "Graph Walk",
        "message": "Explore the knowledge graph to find my connections and relationships. What entities are linked to me?",
        "expected_tool": "graph_walk",
        "category": "graph"
    },
    {
        "name": "Common Ground",
        "message": "What do we have in common? What interests do we share?",
        "expected_tool": "common_ground",
        "category": "graph"
    },
    {
        "name": "Character Evolution",
        "message": "How have I changed over time? How has our relationship evolved?",
        "expected_tool": "char_evolve",
        "category": "graph"
    },

    # Bot Inner Life Tests
    {
        "name": "Search My Thoughts",
        "message": "What have you been dreaming about? Any interesting observations about me?",
        "expected_tool": "search_my_thoughts",
        "category": "inner_life"
    },

    # Document Tests
    {
        "name": "Read Document",
        "message": "I uploaded a file. Can you read DESIGN_SPEC.md and tell me what you think?",
        "expected_tool": "read_document",
        "category": "document"
    },

    # Image Generation Tests
    {
        "name": "Image Generation",
        "message": "Can you draw me a picture of a sunset over mountains? Make it cinematic.",
        "expected_tool": "generate_image",
        "category": "creative"
    },
    {
        "name": "Self Portrait",
        "message": "Generate an image of yourself. What do you look like?",
        "expected_tool": "generate_image",
        "category": "creative"
    },

    # Web Tools Tests
    {
        "name": "Web Search",
        "message": "What's the latest news about AI? Search the web for me.",
        "expected_tool": "web_search",
        "category": "web"
    },
    {
        "name": "Read Web Page",
        "message": "Can you read this article? https://example.com/article and summarize it?",
        "expected_tool": "read_web_page",
        "category": "web"
    },

    # Discord Tools Tests
    {
        "name": "Channel Search",
        "message": "Search the channel for discussions about Python.",
        "expected_tool": "chan_search",
        "category": "discord"
    },
    {
        "name": "User Search",
        "message": "What has @alice been saying? Search her messages.",
        "expected_tool": "user_search",
        "category": "discord"
    },
    {
        "name": "Message Context",
        "message": "What was the context around message 123456789? Show me surrounding messages.",
        "expected_tool": "msg_context",
        "category": "discord"
    },
    {
        "name": "Recent Messages",
        "message": "What's been happening recently in this channel?",
        "expected_tool": "recent_msgs",
        "category": "discord"
    },

    # Introspection Tests
    {
        "name": "Conversation Patterns",
        "message": "Analyze my conversation patterns from the past week. What trends do you see?",
        "expected_tool": "conv_patterns",
        "category": "introspection"
    },
    {
        "name": "Theme Detection",
        "message": "Detect recurring themes about work and hobbies in our conversations. What patterns appear?",
        "expected_tool": "find_themes",
        "category": "introspection"
    },

    # Context Tests
    {
        "name": "Planet Context",
        "message": "Tell me about this server. Who's here? What's it about?",
        "expected_tool": "planet_ctx",
        "category": "context"
    },
    {
        "name": "Universe Overview",
        "message": "What servers are you in? Give me an overview of your universe.",
        "expected_tool": "universe",
        "category": "context"
    },
    {
        "name": "Sibling Info",
        "message": "Tell me about your bot siblings. What are the other bots like?",
        "expected_tool": "sibling_info",
        "category": "context"
    },

    # Utility Tests
    {
        "name": "Active Goals",
        "message": "What goals are we currently working on? What am I trying to accomplish?",
        "expected_tool": "check_goals",
        "category": "utility"
    },
    {
        "name": "Calculator",
        "message": "What's 42 * 12? Can you do some math?",
        "expected_tool": "calculator",
        "category": "utility"
    },
    {
        "name": "Conversation Analysis",
        "message": "Analyze my conversation patterns over the last 48 hours. What are my communication trends?",
        "expected_tool": "conv_patterns",
        "category": "introspection"
    },

    # Complex Multi-Tool Tests
    {
        "name": "Complex Query (Memory + Analysis)",
        "message": "I need you to remember what I told you about machine learning in our past conversations. Search for those specific memories.",
        "expected_tool": "mem_search",  # Should start with memory search
        "category": "complex"
    },
    {
        "name": "Complex Query (Facts + Web)",
        "message": "What are my known interests, and can you search the web for trending topics related to those interests?",
        "expected_tool": "lookup_user_facts",  # Should start with facts
        "category": "complex"
    },
    {
        "name": "Complex Query (Document + Image)",
        "message": "Read the file DESIGN_SPEC.md and generate an illustration based on the key concepts in it.",
        "expected_tool": "read_document",
        "category": "complex"
    },
]


# =============================================================================
# TEST RUNNER - SAME AS ORIGINAL BUT WITH COMPREHENSIVE TOOLS
# =============================================================================

class ComprehensiveLLMToolTester:
    def __init__(self, base_url: str, model: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key or "not-needed"  # Use provided key or default for local
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=self.api_key
        )
        self.results = []
        self._detected_model = None
        self.category_results = {}

    async def get_model_info(self) -> dict:
        """Fetch loaded model info from LM Studio."""
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
                model=self.model or self._detected_model or "gpt-3.5-turbo",
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
                    status = "PARTIAL"  # Called a tool but wrong one
                
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
                # No tool called when one was expected
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

    async def test_langchain_integration(self) -> dict:
        """Test LangChain bind_tools() integration."""
        if not LANGCHAIN_AVAILABLE:
            print("\n❌ LangChain not available. Install with: pip install langchain-openai")
            return {"success": False, "error": "LangChain not installed"}
        
        print("\n" + "=" * 80)
        print("🔗 LANGCHAIN bind_tools() INTEGRATION TEST")
        print("=" * 80)
        print("\nTesting the EXACT pattern WhisperEngine uses in production.\n")
        
        results = {"success": True, "tests": []}
        
        try:
            # Create LLM with LangChain
            llm = ChatOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model or self._detected_model or "gpt-3.5-turbo",
                temperature=0.7
            )
            
            # Bind tools
            llm_with_tools = llm.bind_tools(LANGCHAIN_TOOLS)
            
            # Test cases
            langchain_tests = [
                {
                    "name": "Memory Search",
                    "message": "Do you remember when I told you about my cat?",
                    "expected_tool": "mem_search"
                },
                {
                    "name": "Fact Lookup",
                    "message": "What do you know about me?",
                    "expected_tool": "lookup_user_facts"
                },
                {
                    "name": "Image Generation",
                    "message": "Draw me a sunset over mountains",
                    "expected_tool": "generate_image"
                },
                {
                    "name": "No Tool Needed",
                    "message": "Hello! How are you?",
                    "expected_tool": None
                }
            ]
            
            for test in langchain_tests:
                test_result = {"name": test["name"], "expected_tool": test["expected_tool"]}
                
                try:
                    messages = [HumanMessage(content=f"[User ID: test_user]\n\n{test['message']}")]
                    response = await llm_with_tools.ainvoke(messages)
                    
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        tool_call = response.tool_calls[0]
                        tool_name = tool_call.get('name', 'unknown')
                        test_result["tool_called"] = tool_name
                        
                        if test["expected_tool"] is None:
                            test_result["status"] = "warning"
                            print(f"  ⚠️ {test['name']} - tool called when not expected")
                        elif tool_name == test["expected_tool"]:
                            test_result["status"] = "pass"
                            print(f"  ✅ {test['name']}")
                        else:
                            test_result["status"] = "wrong_tool"
                            print(f"  ❌ {test['name']} - expected {test['expected_tool']}, got {tool_name}")
                    else:
                        if test["expected_tool"] is None:
                            test_result["status"] = "pass"
                            print(f"  ✅ {test['name']} - responded without tools")
                        else:
                            test_result["status"] = "fail"
                            print(f"  ❌ {test['name']} - no tool called")
                            
                except Exception as e:
                    test_result["status"] = "error"
                    test_result["error"] = str(e)
                    print(f"  💥 {test['name']} - error: {str(e)[:50]}")
                
                results["tests"].append(test_result)
            
            # Summary
            passed = sum(1 for t in results["tests"] if t["status"] == "pass")
            failed = sum(1 for t in results["tests"] if t["status"] in ["fail", "wrong_tool", "error"])
            
            print(f"\n{'─' * 80}")
            print(f"📊 LangChain Results: {passed}/{len(results['tests'])} passed")
            
            if passed == len(results["tests"]):
                print("🎉 VERDICT: LangChain bind_tools() fully compatible!")
                results["compatible"] = True
            elif passed >= len(results["tests"]) * 0.5:
                print("⚡ VERDICT: Mostly compatible with minor issues")
                results["compatible"] = True
            else:
                print("❌ VERDICT: Not compatible with LangChain bind_tools()")
                results["compatible"] = False
            print("=" * 80)
            
        except Exception as e:
            print(f"\n💥 Critical error: {e}")
            results["success"] = False
            results["error"] = str(e)
        
        return results

    async def run_all_tests(self) -> None:
        """Run all comprehensive tests."""
        print("=" * 80)
        print("🧪 COMPREHENSIVE LLM API TOOL CALLING TEST")
        print("=" * 80)
        
        model_info = await self.get_model_info()
        print(f"\n📡 Endpoint: {self.base_url}")
        print(f"🤖 Model: {self.model or model_info.get('id', 'Unknown')}")
        print(f"📚 Testing {len(COMPREHENSIVE_TEST_CASES)} test cases across {len(WHISPERENGINE_COMPREHENSIVE_TOOLS)} tools\n")
        
        print("─" * 80)
        print("Running tests...\n")
        
        # Run tests
        for test_case in COMPREHENSIVE_TEST_CASES:
            result = await self.test_tool_calling(test_case)
            self.results.append(result)
            
            # Print progress
            status_symbol = "✅" if result["status"] == "PASS" else ("⚠️" if result["status"] == "PARTIAL" else "❌")
            print(f"  {status_symbol} {result['name']}")
            
            # Track by category
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
        
        # Overall stats
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        
        print(f"  ✅ Passed:  {passed}/{len(self.results)}")
        print(f"  ⚠️ Partial: {partial}/{len(self.results)}")
        print(f"  ❌ Failed:  {failed}/{len(self.results)}")
        print(f"  💥 Errors:  {errors}/{len(self.results)}\n")
        
        # By category
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
            status_icon = {"PASS": "✅", "PARTIAL": "⚠️", "FAIL": "❌", "ERROR": "💥"}.get(result["status"], "❓")
            print(f"[{result['status']}] {result['name']}")
            if result["status"] != "PASS":
                if result["tool_called"]:
                    print(f"  Expected: {result['expected_tool']}, Got: {result['tool_called']}")
                else:
                    print(f"  Expected: {result['expected_tool']}, Got: No tool called")
            if "error" in result:
                print(f"  Error: {result['error']}")
            print()
        
        # Overall verdict
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
        description="Comprehensive LLM API tool calling compatibility test for WhisperEngine"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:1234/v1",
        help="Base URL of LLM API endpoint (default: http://localhost:1234/v1 for LM Studio)"
    )
    parser.add_argument(
        "--model",
        help="Specific model to test (optional, auto-detects if not specified)"
    )
    parser.add_argument(
        "--api-key",
        help="API key for cloud providers (OpenRouter, OpenAI, etc.). For local endpoints, this is ignored."
    )
    parser.add_argument(
        "--langchain",
        action="store_true",
        help="Test LangChain bind_tools() integration (WhisperEngine production pattern)"
    )
    
    args = parser.parse_args()
    
    tester = ComprehensiveLLMToolTester(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key
    )
    
    if args.langchain:
        # Run LangChain tests only
        await tester.get_model_info()  # Detect model first
        await tester.test_langchain_integration()
    else:
        # Run native function calling tests
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
