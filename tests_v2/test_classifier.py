import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.agents.classifier import ComplexityClassifier

from langchain_core.messages import HumanMessage, AIMessage

@pytest.mark.asyncio
async def test_classifier_simple():
    with patch("src_v2.agents.classifier.create_llm") as mock_create_llm:
        # Setup mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "SIMPLE"
        mock_llm.ainvoke.return_value = mock_response
        mock_create_llm.return_value = mock_llm

        classifier = ComplexityClassifier()
        result = await classifier.classify("Hi there!")
        
        assert result == "SIMPLE"
        mock_llm.ainvoke.assert_called_once()

@pytest.mark.asyncio
async def test_classifier_with_history():
    with patch("src_v2.agents.classifier.create_llm") as mock_create_llm:
        # Setup mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "COMPLEX"
        mock_llm.ainvoke.return_value = mock_response
        mock_create_llm.return_value = mock_llm

        classifier = ComplexityClassifier()
        history = [
            HumanMessage(content="I'm feeling sad."),
            AIMessage(content="I'm sorry to hear that. Why?"),
        ]
        result = await classifier.classify("It reminds me of my childhood.", history)
        
        assert result == "COMPLEX_MID"
        
        # Verify history was included in the prompt
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Recent Chat History" in call_args[1].content
        assert "I'm feeling sad" in call_args[1].content

@pytest.mark.asyncio
async def test_classifier_complex():
    with patch("src_v2.agents.classifier.create_llm") as mock_create_llm:
        # Setup mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "COMPLEX_HIGH"
        mock_llm.ainvoke.return_value = mock_response
        mock_create_llm.return_value = mock_llm

        classifier = ComplexityClassifier()
        result = await classifier.classify("What is the meaning of life and how does it relate to our past conversations?")
        
        assert result == "COMPLEX_HIGH"

@pytest.mark.asyncio
async def test_classifier_error_handling():
    with patch("src_v2.agents.classifier.create_llm") as mock_create_llm:
        # Setup mock LLM to raise exception
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("API Error")
        mock_create_llm.return_value = mock_llm

        classifier = ComplexityClassifier()
        result = await classifier.classify("Anything")
        
        # Should fallback to SIMPLE
        assert result == "SIMPLE"
