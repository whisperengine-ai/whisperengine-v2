"""add_metadata_to_chat_history

Revision ID: add_metadata_col
Revises: a951f92c5e06
Create Date: 2025-12-19 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_metadata_col'
down_revision: Union[str, None] = 'a951f92c5e06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add metadata column to v2_chat_history
    op.add_column('v2_chat_history', sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True))


def downgrade() -> None:
    op.drop_column('v2_chat_history', 'metadata')
