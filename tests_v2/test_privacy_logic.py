import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.universe.privacy import PrivacyManager
from src_v2.knowledge.manager import KnowledgeManager

@pytest.mark.asyncio
async def test_privacy_manager_get_settings_defaults():
    """Test that get_settings returns defaults when DB is not available or user not found."""
    privacy_manager = PrivacyManager()
    
    # Mock db_manager
    with patch('src_v2.universe.privacy.db_manager') as mock_db:
        mock_db.postgres_pool = None
        
        settings = await privacy_manager.get_settings("user123")
        assert settings["share_with_other_bots"] is True
        assert settings["invisible_mode"] is False

@pytest.mark.asyncio
async def test_privacy_manager_get_settings_from_db():
    """Test retrieving settings from DB."""
    privacy_manager = PrivacyManager()
    
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Mock DB return value
    mock_conn.fetchrow.return_value = {
        "share_with_other_bots": False,
        "share_across_planets": True,
        "allow_bot_introductions": True,
        "invisible_mode": True
    }
    
    with patch('src_v2.universe.privacy.db_manager') as mock_db:
        mock_db.postgres_pool = mock_pool
        
        settings = await privacy_manager.get_settings("user123")
        assert settings["share_with_other_bots"] is False
        assert settings["invisible_mode"] is True

@pytest.mark.asyncio
async def test_knowledge_manager_privacy_injection():
    """Test that KnowledgeManager injects privacy constraints into Cypher generation."""
    knowledge_manager = KnowledgeManager()
    
    # Mock privacy_manager
    with patch('src_v2.knowledge.manager.privacy_manager') as mock_privacy:
        # Case 1: Privacy Restricted (share_with_other_bots = False)
        # Configure get_settings to be awaitable
        mock_privacy.get_settings = AsyncMock(return_value={
            "share_with_other_bots": False
        })
        
        # Mock LLM chain
        knowledge_manager.cypher_chain = AsyncMock()
        knowledge_manager.cypher_chain.ainvoke.return_value = "MATCH (n) RETURN n"
        
        # Mock DB driver to avoid errors
        with patch('src_v2.knowledge.manager.db_manager') as mock_db:
            mock_db.neo4j_driver = MagicMock()
            mock_session = AsyncMock()
            mock_db.neo4j_driver.session.return_value.__aenter__.return_value = mock_session
            mock_session.run.return_value.data.return_value = []
            
            await knowledge_manager.query_graph("user123", "What do you know about me?", bot_name="Elena")
            
            # Verify that privacy instructions were passed to the LLM chain
            call_args = knowledge_manager.cypher_chain.ainvoke.call_args[0][0]
            assert "PRIVACY RESTRICTION ENABLED" in call_args["privacy_instructions"]
            assert "r.source_bot = $bot_name" in call_args["privacy_instructions"]

@pytest.mark.asyncio
async def test_knowledge_manager_privacy_open():
    """Test that KnowledgeManager allows all access when privacy is open."""
    knowledge_manager = KnowledgeManager()
    
    # Mock privacy_manager
    with patch('src_v2.knowledge.manager.privacy_manager') as mock_privacy:
        # Case 2: Privacy Open (share_with_other_bots = True)
        # Configure get_settings to be awaitable
        mock_privacy.get_settings = AsyncMock(return_value={
            "share_with_other_bots": True
        })
        
        # Mock LLM chain
        knowledge_manager.cypher_chain = AsyncMock()
        knowledge_manager.cypher_chain.ainvoke.return_value = "MATCH (n) RETURN n"
        
        # Mock DB driver
        with patch('src_v2.knowledge.manager.db_manager') as mock_db:
            mock_db.neo4j_driver = MagicMock()
            mock_session = AsyncMock()
            mock_db.neo4j_driver.session.return_value.__aenter__.return_value = mock_session
            mock_session.run.return_value.data.return_value = []
            
            await knowledge_manager.query_graph("user123", "What do you know about me?", bot_name="Elena")
            
            # Verify that privacy instructions were empty or permissive
            call_args = knowledge_manager.cypher_chain.ainvoke.call_args[0][0]
            assert call_args["privacy_instructions"] == ""
