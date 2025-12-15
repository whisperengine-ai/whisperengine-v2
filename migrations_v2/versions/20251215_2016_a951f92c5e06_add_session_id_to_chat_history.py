"""add_session_id_to_chat_history

Revision ID: a951f92c5e06
Revises: adr014_author
Create Date: 2025-12-15 20:16:55.643877+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a951f92c5e06'
down_revision: Union[str, None] = 'adr014_author'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add session_id column to v2_chat_history
    op.add_column('v2_chat_history', sa.Column('session_id', sa.String(), nullable=True))
    
    # Create an index for faster lookups by session_id
    op.create_index('ix_v2_chat_history_session_id', 'v2_chat_history', ['session_id'])


def downgrade() -> None:
    # Remove index and column
    op.drop_index('ix_v2_chat_history_session_id', table_name='v2_chat_history')
    op.drop_column('v2_chat_history', 'session_id')
