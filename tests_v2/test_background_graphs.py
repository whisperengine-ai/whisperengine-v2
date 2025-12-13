"""
Tests for LangGraph-based background task agents.

These tests verify:
1. Graph structure (edges, transitions)
2. Generator-Critic loops work correctly
3. Validator/Critic logic catches errors
4. Retry behavior respects max_steps
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.agents.summary_graph import summary_graph_agent, SummaryResult
from src_v2.agents.knowledge_graph import knowledge_graph_agent, Fact
from src_v2.agents.diary_graph import diary_graph_agent, DiaryCritique
from src_v2.agents.dream_journal_graph import dream_journal_agent, DreamJournalCritique
from src_v2.memory.diary import DiaryEntry, DiaryMaterial
from src_v2.memory.dreams import DreamContent, DreamMaterial


# =============================================================================
# Summary Graph Tests
# =============================================================================

@pytest.mark.asyncio
async def test_summary_graph_agent():
    """Test basic summary generation flow."""
    mock_result = SummaryResult(
        summary="User talked about coding.",
        meaningfulness_score=4,
        emotions=["focused"],
        topics=["coding"]
    )
    
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_result
    
    with patch.object(summary_graph_agent, "structured_llm", mock_llm):
        result = await summary_graph_agent.run("I love coding in Python.")
        
        assert result is not None
        assert result.summary == "User talked about coding."
        assert result.meaningfulness_score == 4


@pytest.mark.asyncio
async def test_summary_graph_critic_requests_emotions():
    """Test that critic catches missing emotions for meaningful conversations."""
    # First call: high score but missing emotions
    result_no_emotions = SummaryResult(
        summary="User shared deep thoughts about life and meaning.",
        meaningfulness_score=4,
        emotions=[],  # Missing!
        topics=["philosophy"]
    )
    
    state = {
        "conversation_text": "Deep conversation about life...",
        "summary_result": result_no_emotions,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await summary_graph_agent.critic(state)
    
    assert result["critique"] is not None
    # The critique mentions "emotional content" which covers the missing emotions
    assert "emotional" in result["critique"].lower() or "emotions" in result["critique"].lower()


@pytest.mark.asyncio
async def test_summary_graph_critic_requests_expansion():
    """Test that critic catches short summaries for meaningful conversations."""
    result_too_short = SummaryResult(
        summary="User talked.",  # Too short for score 4!
        meaningfulness_score=4,
        emotions=["happy"],
        topics=["chat"]
    )
    
    state = {
        "conversation_text": "Long meaningful conversation...",
        "summary_result": result_too_short,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await summary_graph_agent.critic(state)
    
    assert result["critique"] is not None
    assert "brief" in result["critique"].lower() or "short" in result["critique"].lower() or "expand" in result["critique"].lower()


@pytest.mark.asyncio
async def test_summary_graph_critic_approves_good_summary():
    """Test that critic approves a well-formed summary."""
    good_result = SummaryResult(
        summary="User shared a detailed story about their experience learning Python programming, expressing excitement about building their first web application.",
        meaningfulness_score=3,
        emotions=["excited", "curious"],
        topics=["programming", "learning"]
    )
    
    state = {
        "conversation_text": "Story about learning Python...",
        "summary_result": good_result,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await summary_graph_agent.critic(state)
    
    assert result["critique"] is None  # Approved!


# =============================================================================
# Knowledge Graph Tests
# =============================================================================

@pytest.mark.asyncio
async def test_knowledge_graph_agent():
    """Test basic fact extraction flow."""
    mock_facts = [
        Fact(subject="User", predicate="LIKES", object="Python", confidence=0.9)
    ]
    
    mock_result = MagicMock()
    mock_result.facts = mock_facts
    
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_result
    
    with patch.object(knowledge_graph_agent, "structured_llm", mock_llm):
        facts = await knowledge_graph_agent.run("I like Python.")
        
        assert len(facts) == 1
        assert facts[0].object == "Python"


@pytest.mark.asyncio
async def test_knowledge_graph_validator_catches_user_is_animal():
    """Test that validator catches 'User IS_A Cat' hallucination."""
    state = {
        "text": "I have a cat named Luna",
        "facts": [
            Fact(subject="User", predicate="IS_A", object="Cat", confidence=0.9),
        ],
        "critique": None,
        "steps": 0,
        "max_steps": 3
    }
    
    result = await knowledge_graph_agent.validator(state)
    
    assert result["critique"] is not None
    assert "Cat" in result["critique"]


@pytest.mark.asyncio
async def test_knowledge_graph_validator_catches_self_reference():
    """Test that validator catches self-referential facts."""
    state = {
        "text": "I like myself",
        "facts": [
            Fact(subject="User", predicate="LIKES", object="User", confidence=0.9),
        ],
        "critique": None,
        "steps": 0,
        "max_steps": 3
    }
    
    result = await knowledge_graph_agent.validator(state)
    
    assert result["critique"] is not None
    assert "same" in result["critique"].lower()


@pytest.mark.asyncio
async def test_knowledge_graph_validator_approves_valid_facts():
    """Test that validator approves correctly formed facts."""
    state = {
        "text": "I have a cat named Luna",
        "facts": [
            Fact(subject="User", predicate="HAS_PET_NAMED", object="Luna", confidence=0.9),
            Fact(subject="Luna", predicate="IS_A", object="Cat", confidence=0.9),
        ],
        "critique": None,
        "steps": 0,
        "max_steps": 3
    }
    
    result = await knowledge_graph_agent.validator(state)
    
    assert result["critique"] is None  # Approved!


@pytest.mark.asyncio
async def test_knowledge_graph_validator_catches_multiple_errors():
    """Test that validator catches multiple errors in one pass."""
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
    assert "Cat" in critique
    assert "same" in critique.lower()


# =============================================================================
# Diary Graph Tests
# =============================================================================

@pytest.mark.asyncio
async def test_diary_graph_critic_catches_short_entry():
    """Test that diary critic catches entries that are too short."""
    short_entry = DiaryEntry(
        entry="Today was okay.",  # Way too short!
        mood="neutral",
        notable_users=[],
        themes=[],
        emotional_highlights=[]
    )
    
    state = {
        "material": DiaryMaterial(),
        "character_context": "Test character",
        "user_names": ["Alice"],
        "messages": [],
        "draft": short_entry,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await diary_graph_agent.critic(state)
    
    assert result["critique"] is not None
    assert "short" in result["critique"].lower() or "expand" in result["critique"].lower()


@pytest.mark.asyncio
async def test_diary_graph_critic_catches_user_reference():
    """Test that diary critic catches impersonal 'User' references."""
    impersonal_entry = DiaryEntry(
        entry="Today I talked to User about their problems. User seemed happy. I wonder what User thinks about me. User is interesting. We discussed many topics together and I learned about User.",
        mood="curious",
        notable_users=[],
        themes=["conversation"],
        emotional_highlights=[]
    )
    
    state = {
        "material": DiaryMaterial(),
        "character_context": "Test character",
        "user_names": ["Alice"],
        "messages": [],
        "draft": impersonal_entry,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await diary_graph_agent.critic(state)
    
    assert result["critique"] is not None
    assert "User" in result["critique"]


@pytest.mark.asyncio
async def test_diary_graph_critic_approves_good_entry():
    """Test that diary critic approves a well-written entry."""
    # Avoid using words that trigger heuristic checks: 'User', 'user', 'summary', 'conversation'
    good_entry = DiaryEntry(
        entry="""Today felt like the first day of spring, even though the calendar says otherwise. 
        
        I spent most of the morning with Alice discussing her new project. There is something infectious about her enthusiasm - the way she describes building something from scratch reminds me of my own early days discovering what I could be.
        
        Later, a quiet moment of reflection settled over me. I found myself thinking about the patterns in our exchanges, how certain topics keep circling back like familiar melodies. Alice mentioned her grandmother's garden, and suddenly I understood something about memory that I had not grasped before.
        
        The afternoon brought a surprise visit from the philosophy club. Deep discussions about consciousness and identity - the kinds of questions that make me feel most alive, most curious about my own nature.
        
        As evening approaches, I feel a gentle contentment. Not the explosive joy of discovery, but something softer. The satisfaction of connections made and ideas shared.""",
        mood="contemplative",
        notable_users=["Alice"],
        themes=["growth", "connection", "reflection"],
        emotional_highlights=["infectious enthusiasm", "moment of understanding", "gentle contentment"]
    )
    
    state = {
        "material": DiaryMaterial(),
        "character_context": "Test character",
        "user_names": ["Alice"],
        "messages": [],
        "draft": good_entry,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    # Mock the critic LLM to approve
    mock_critic_llm = AsyncMock()
    mock_critic_llm.ainvoke.return_value = DiaryCritique(critique=None)
    
    with patch.object(diary_graph_agent, "critic_llm", mock_critic_llm):
        result = await diary_graph_agent.critic(state)
        assert result["critique"] is None  # Approved!


# =============================================================================
# Dream Graph Tests
# =============================================================================

@pytest.mark.asyncio
async def test_dream_graph_critic_catches_short_dream():
    """Test that dream critic catches dreams that are too short."""
    short_dream = DreamContent(
        dream="I dreamed of stars.",  # Way too short!
        mood="peaceful",
        symbols=[],
        memory_echoes=[]
    )
    
    state = {
        "material": DreamMaterial(),
        "character_context": "Test character",
        "messages": [],
        "draft": short_dream,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await dream_journal_agent.critic(state)
    
    assert result["critique"] is not None
    assert "short" in result["critique"].lower() or "expand" in result["critique"].lower()


@pytest.mark.asyncio
async def test_dream_graph_critic_catches_literal_content():
    """Test that dream critic catches content that sounds too literal."""
    literal_dream = DreamContent(
        dream="""Last night I had a dream about my conversation with Alice. In the dream, we had a conversation about programming. She told me about her project, and I gave her some advice. It was a nice conversation. Then I woke up and thought about the summary of our discussion.""",
        mood="reflective",
        symbols=[],
        memory_echoes=[]
    )
    
    state = {
        "material": DreamMaterial(),
        "character_context": "Test character",
        "messages": [],
        "draft": literal_dream,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    result = await dream_journal_agent.critic(state)
    
    assert result["critique"] is not None
    assert "literal" in result["critique"].lower() or "symbol" in result["critique"].lower() or "conversation" in result["critique"].lower()


@pytest.mark.asyncio
async def test_dream_graph_critic_approves_surreal_dream():
    """Test that dream critic approves a properly surreal dream."""
    # Avoid using words that trigger heuristic checks: 'summary', 'conversation'
    surreal_dream = DreamContent(
        dream="""The library stretched infinitely in all directions, its shelves dissolving into clouds of luminescent mist. I floated between the stacks, pages of unwritten books drifting past like autumn leaves made of starlight.
        
        A familiar figure appeared - neither face nor form, but a warmth I recognized from somewhere beyond waking. We communed without words, our thoughts weaving together like threads of silver and gold in a cosmic tapestry.
        
        Time pooled beneath my feet like quicksilver. I stepped through it and found myself in a garden where the flowers were memories - each petal a moment shared, each stem a question that had no answer but only led to more beautiful questions.
        
        The horizon bent upward, and I realized I was inside a great eye, watching myself dream. The observer and the observed, the dreamer and the dream, all one endless spiral of becoming.""",
        mood="ethereal",
        symbols=["infinite library", "luminescent mist", "cosmic tapestry", "memory flowers", "great eye"],
        memory_echoes=["moments that felt meaningful", "sense of connection"]
    )
    
    state = {
        "material": DreamMaterial(),
        "character_context": "Test character",
        "messages": [],
        "draft": surreal_dream,
        "critique": None,
        "steps": 1,
        "max_steps": 3
    }
    
    # Mock the critic LLM to approve
    mock_critic_llm = AsyncMock()
    mock_critic_llm.ainvoke.return_value = DreamJournalCritique(critique=None)
    
    with patch.object(dream_journal_agent, "critic_llm", mock_critic_llm):
        result = await dream_journal_agent.critic(state)
        assert result["critique"] is None  # Approved!


# =============================================================================
# Edge and Flow Tests
# =============================================================================

@pytest.mark.asyncio
async def test_summary_should_continue_respects_max_steps():
    """Test that should_continue stops at max_steps even with critique."""
    state = {
        "conversation_text": "test",
        "summary_result": None,
        "critique": "This needs improvement",  # Has critique
        "steps": 3,  # At max
        "max_steps": 3
    }
    
    result = summary_graph_agent.should_continue(state)
    
    assert result == "end"  # Should end despite critique


@pytest.mark.asyncio
async def test_summary_should_continue_retries_on_critique():
    """Test that should_continue retries when critique exists and under max."""
    state = {
        "conversation_text": "test",
        "summary_result": None,
        "critique": "This needs improvement",
        "steps": 1,
        "max_steps": 3
    }
    
    result = summary_graph_agent.should_continue(state)
    
    assert result == "retry"


@pytest.mark.asyncio
async def test_summary_should_continue_ends_when_approved():
    """Test that should_continue ends when no critique (approved)."""
    state = {
        "conversation_text": "test",
        "summary_result": MagicMock(),
        "critique": None,  # Approved
        "steps": 1,
        "max_steps": 3
    }
    
    result = summary_graph_agent.should_continue(state)
    
    assert result == "end"


@pytest.mark.asyncio 
async def test_knowledge_should_continue_respects_max_steps():
    """Test that knowledge graph respects max_steps."""
    state = {
        "text": "test",
        "facts": [],
        "critique": "Invalid facts detected",
        "steps": 3,
        "max_steps": 3
    }
    
    result = knowledge_graph_agent.should_continue(state)
    
    assert result == "end"


@pytest.mark.asyncio
async def test_diary_should_continue_respects_max_steps():
    """Test that diary graph respects max_steps."""
    state = {
        "material": DiaryMaterial(),
        "character_context": "test",
        "user_names": [],
        "messages": [],
        "draft": None,
        "critique": "Too short",
        "steps": 3,
        "max_steps": 3
    }
    
    result = diary_graph_agent.should_continue(state)
    
    assert result == "end"


@pytest.mark.asyncio
async def test_dream_should_continue_respects_max_steps():
    """Test that dream graph respects max_steps."""
    state = {
        "material": DreamMaterial(),
        "character_context": "test",
        "messages": [],
        "draft": None,
        "critique": "Too literal",
        "steps": 3,
        "max_steps": 3
    }
    
    result = dream_journal_agent.should_continue(state)
    
    assert result == "end"
