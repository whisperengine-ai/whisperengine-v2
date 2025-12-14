"""Add author tracking fields to v2_chat_history

Revision ID: adr014_author
Revises: rm_reminders
Create Date: 2025-12-13 14:00:00.000000

ADR-014: Multi-Party Data Model - Phase 1

Adds author_id, author_is_bot, and reply_to_msg_id columns to support
proper bot-to-bot conversations and message attribution.

The current schema conflates "conversation partner" (user_id) with 
"message author". This migration separates them:
- user_id: WHO the bot is talking WITH (conversation context)
- author_id: WHO wrote THIS specific message
- author_is_bot: Is the author a bot?
- reply_to_msg_id: Discord message ID this is replying to (threading)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adr014_author'
down_revision: Union[str, None] = 'rm_reminders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for author tracking
    op.add_column('v2_chat_history', 
        sa.Column('author_id', sa.Text(), nullable=True))
    op.add_column('v2_chat_history', 
        sa.Column('author_is_bot', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('v2_chat_history', 
        sa.Column('reply_to_msg_id', sa.Text(), nullable=True))
    
    # Create indexes for efficient queries
    op.create_index(
        'idx_v2_chat_history_author', 
        'v2_chat_history', 
        ['author_id'], 
        unique=False
    )
    op.create_index(
        'idx_v2_chat_history_author_bot', 
        'v2_chat_history', 
        ['author_id', 'author_is_bot'], 
        unique=False
    )
    
    # Backfill existing data based on role
    # For 'human' role: author is the user_id
    # For 'ai' role: author is the character_name (bot name, not Discord ID yet)
    op.execute("""
        UPDATE v2_chat_history 
        SET 
            author_id = CASE 
                WHEN role = 'human' THEN user_id
                WHEN role = 'ai' THEN character_name
                WHEN role = 'assistant' THEN character_name
                ELSE user_id
            END,
            author_is_bot = CASE
                WHEN role = 'ai' THEN true
                WHEN role = 'assistant' THEN true
                ELSE false
            END
        WHERE author_id IS NULL
    """)


def downgrade() -> None:
    op.drop_index('idx_v2_chat_history_author_bot', table_name='v2_chat_history')
    op.drop_index('idx_v2_chat_history_author', table_name='v2_chat_history')
    op.drop_column('v2_chat_history', 'reply_to_msg_id')
    op.drop_column('v2_chat_history', 'author_is_bot')
    op.drop_column('v2_chat_history', 'author_id')
