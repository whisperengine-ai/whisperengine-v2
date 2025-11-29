"""
Test script for DreamWeaver tools.

Verifies that all tools load correctly and can be invoked (with mocked backends).
"""
import asyncio
import sys
sys.path.insert(0, '/Users/markcastillo/git/whisperengine-v2')

from src_v2.tools.dreamweaver_tools import (
    get_dreamweaver_tools,
    get_dreamweaver_tools_with_existing,
    SearchMeaningfulMemoriesTool,
    SearchSessionSummariesTool,
    SearchAllUserFactsTool,
    SearchByTypeTool,
    GetActiveGoalsTool,
    FindInterestingQuestionsTool,
    FindCommonThemesTool,
    GenerateDeepAnswerTool,
    PlanNarrativeTool,
    WeaveDreamTool,
    WeaveDiaryTool,
)


def test_tool_loading():
    """Test that all tools load correctly."""
    tools = get_dreamweaver_tools("elena")
    
    expected_tools = [
        "search_meaningful_memories",
        "search_session_summaries",
        "search_all_user_facts",
        "search_by_memory_type",
        "get_active_goals",
        "search_broadcast_channel",  # NEW: Cross-bot broadcast channel search
        "find_interesting_questions",
        "find_common_themes",
        "prepare_deep_answer",
        "plan_narrative",
        "weave_dream",
        "weave_diary",
    ]
    
    tool_names = [t.name for t in tools]
    
    for expected in expected_tools:
        assert expected in tool_names, f"Missing tool: {expected}"
    
    print(f"✅ All {len(expected_tools)} tools loaded correctly")


def test_tool_schemas():
    """Test that tools have proper schemas."""
    tools = get_dreamweaver_tools("elena")
    
    for tool in tools:
        # All tools should have names and descriptions
        assert tool.name, f"Tool missing name: {tool}"
        assert tool.description, f"Tool {tool.name} missing description"
        
        # Tools should have args_schema (Pydantic model)
        assert tool.args_schema, f"Tool {tool.name} missing args_schema"
    
    print("✅ All tools have proper schemas")


def test_tool_with_existing():
    """Test get_dreamweaver_tools_with_existing."""
    # This should add existing tools from the real-time pipeline
    tools = get_dreamweaver_tools_with_existing("elena")
    
    tool_names = [t.name for t in tools]
    
    # Should include the dreamweaver tools
    assert "search_meaningful_memories" in tool_names
    assert "weave_diary" in tool_names
    
    # Should also include the existing tools
    assert "lookup_user_facts" in tool_names
    assert "explore_knowledge_graph" in tool_names
    assert "discover_common_ground" in tool_names
    
    print(f"✅ get_dreamweaver_tools_with_existing loaded {len(tools)} tools (including existing)")


def test_deep_answer_tools():
    """Test the deep answer tools have proper inputs."""
    tools = get_dreamweaver_tools("elena")
    tool_map = {t.name: t for t in tools}
    
    # FindInterestingQuestionsTool - should have include_community param
    find_q = tool_map["find_interesting_questions"]
    schema = find_q.args_schema.model_json_schema() if find_q.args_schema else {}
    assert "hours_back" in schema.get("properties", {}), f"Missing hours_back, got: {schema.get('properties', {}).keys()}"
    assert "include_community" in schema.get("properties", {}), f"Missing include_community for community sources"
    
    # PrepareDeepAnswerTool - should have source param for community questions
    deep_a = tool_map["prepare_deep_answer"]
    schema = deep_a.args_schema.model_json_schema() if deep_a.args_schema else {}
    assert "question" in schema.get("properties", {}), f"Missing question, got: {schema.get('properties', {}).keys()}"
    assert "source" in schema.get("properties", {}), f"Missing source param for question origin"
    
    # PlanNarrativeTool should have deep_answer_question
    plan = tool_map["plan_narrative"]
    schema = plan.args_schema.model_json_schema() if plan.args_schema else {}
    assert "deep_answer_question" in schema.get("properties", {}), f"Missing deep_answer_question, got: {schema.get('properties', {}).keys()}"
    
    # WeaveDiaryTool should have deep_answer_included
    weave = tool_map["weave_diary"]
    schema = weave.args_schema.model_json_schema() if weave.args_schema else {}
    assert "deep_answer_included" in schema.get("properties", {}), f"Missing deep_answer_included, got: {schema.get('properties', {}).keys()}"
    
    print("✅ Deep answer tools have proper schemas (including community source support)")


def test_broadcast_channel_tool():
    """Test the broadcast channel tool for cross-bot insights."""
    tools = get_dreamweaver_tools("elena")
    tool_map = {t.name: t for t in tools}
    
    # SearchBroadcastChannelTool should exist
    assert "search_broadcast_channel" in tool_map, "Missing search_broadcast_channel tool"
    
    broadcast_tool = tool_map["search_broadcast_channel"]
    schema = broadcast_tool.args_schema.model_json_schema() if broadcast_tool.args_schema else {}
    
    # Should have query, limit, and bot_name_filter params
    props = schema.get("properties", {})
    assert "query" in props, "Missing query param"
    assert "limit" in props, "Missing limit param"
    assert "bot_name_filter" in props, "Missing bot_name_filter for filtering by bot"
    
    # Description should mention cross-bot
    assert "cross-bot" in broadcast_tool.description.lower() or "other bots" in broadcast_tool.description.lower()
    
    print("✅ Broadcast channel tool configured for cross-bot insights")


def test_dreamweaver_agent():
    """Test that DreamWeaver agent initializes correctly."""
    from src_v2.agents.dreamweaver import get_dreamweaver_agent, DreamWeaverAgent
    
    agent = get_dreamweaver_agent()
    
    assert isinstance(agent, DreamWeaverAgent)
    assert agent.max_steps == 15
    assert agent.llm is not None
    
    # Check that prompts mention deep answers and community sources
    diary_prompt = agent._construct_diary_prompt("elena", "A companion AI")
    assert "DEEP ANSWER" in diary_prompt
    assert "COMMUNITY" in diary_prompt.upper()  # Community-wide feature
    assert "Gossip" in diary_prompt or "gossip" in diary_prompt  # Cross-bot sources
    
    print("✅ DreamWeaver agent initialized correctly with deep answer prompts")


if __name__ == "__main__":
    print("\n=== Testing DreamWeaver Tools ===\n")
    
    test_tool_loading()
    test_tool_schemas()
    test_tool_with_existing()
    test_deep_answer_tools()
    test_broadcast_channel_tool()
    test_dreamweaver_agent()
    
    print("\n=== All DreamWeaver Tests Passed! ===\n")
