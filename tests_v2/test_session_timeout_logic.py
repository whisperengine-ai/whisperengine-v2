import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from uuid import UUID
from src_v2.memory.session import SessionManager

TEST_SESSION_UUID = "00000000-0000-0000-0000-000000000001"

@pytest.mark.asyncio
async def test_get_stale_sessions():
    # Mock db_manager
    with patch('src_v2.memory.session.db_manager') as mock_db:
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_db.postgres_pool = mock_pool
        
        # Setup acquire to return an async context manager
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__.return_value = mock_conn
        mock_context_manager.__aexit__.return_value = None
        
        mock_pool.acquire.return_value = mock_context_manager
        
        # Mock return values
        mock_conn.fetch.return_value = [
            {
                'id': UUID(TEST_SESSION_UUID),
                'user_id': 'user-1',
                'character_name': 'bot-1',
                'start_time': datetime.now(),
                'updated_at': datetime.now() - timedelta(minutes=40)
            }
        ]
        
        manager = SessionManager()
        sessions = await manager.get_stale_sessions(timeout_minutes=30)
        
        assert len(sessions) == 1
        assert sessions[0]['id'] == UUID(TEST_SESSION_UUID)
        
        # Verify SQL query
        args, _ = mock_conn.fetch.call_args
        assert "SELECT id, user_id, character_name" in args[0]
        assert "WHERE is_active = TRUE" in args[0]

@pytest.mark.asyncio
async def test_get_session_messages():
    # Mock db_manager
    with patch('src_v2.memory.session.db_manager') as mock_db:
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_db.postgres_pool = mock_pool
        
        # Setup acquire to return an async context manager
        mock_context_manager = MagicMock()
        mock_context_manager.__aenter__.return_value = mock_conn
        mock_context_manager.__aexit__.return_value = None
        
        mock_pool.acquire.return_value = mock_context_manager
        
        # Mock session fetch
        mock_conn.fetchrow.return_value = {
            'user_id': 'user-1',
            'character_name': 'bot-1',
            'start_time': datetime.now() - timedelta(hours=1),
            'updated_at': datetime.now(),
            'end_time': None,
            'is_active': True
        }
        
        # Mock messages fetch
        mock_conn.fetch.return_value = [
            {
                'role': 'human',
                'content': 'hello',
                'timestamp': datetime.now(),
                'user_name': 'User'
            }
        ]
        
        manager = SessionManager()
        messages = await manager.get_session_messages(TEST_SESSION_UUID)
        
        assert len(messages) == 1
        assert messages[0]['content'] == 'hello'
        
        # Verify SQL queries
        assert mock_conn.fetchrow.called
        assert mock_conn.fetch.called
