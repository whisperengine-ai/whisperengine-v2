import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.agents.summary_graph import summary_graph_agent, SummaryResult
from src_v2.agents.knowledge_graph import knowledge_graph_agent, Fact

@pytest.mark.asyncio
async def test_summary_graph_agent():
    # Mock the LLM response
    mock_result = SummaryResult(
        summary="User talked about coding.",
        meaningfulness_score=4,
        emotions=["focused"],
        topics=["coding"]
    )
    
    # Create a mock for structured_llm
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_result
    
    with patch.object(summary_graph_agent, "structured_llm", mock_llm):
        result = await summary_graph_agent.run("I love coding in Python.")
        
        assert result is not None
        assert result.summary == "User talked about coding."
        assert result.meaningfulness_score == 4

@pytest.mark.asyncio
async def test_knowledge_graph_agent():
    # Mock the LLM response
    mock_facts = [
        Fact(subject="User", predicate="LIKES", object="Python", confidence=0.9)
    ]
    
    # Mock the result object that has a .facts attribute
    mock_result = MagicMock()
    mock_result.facts = mock_facts
    
    # Create a mock for structured_llm
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_result
    
    with patch.object(knowledge_graph_agent, "structured_llm", mock_llm):
        facts = await knowledge_graph_agent.run("I like Python.")
        
        assert len(facts) == 1
        assert facts[0].object == "Python"

@pytest.mark.asyncio
async def test_knowledge_graph_validator():
    # Test the validator logic directly
    state = {
        "text": "dummy",
        "facts": [
            Fact(subject="User", predicate="IS_A", object="Cat", confidence=0.9),
            Fact(subject="User", predicate="LIKES", object="User", confidence=0.9)
        ],
        "critique": None,
        "steps": 0,
        "max_steps": 3
    }
    
    result = await knowledge_graph_agent.validator(state)
    critique = result["critique"]
    
    assert critique is not None
    assert "User cannot be a Cat" in critique
    assert "Subject and Object cannot be the same" in critique
