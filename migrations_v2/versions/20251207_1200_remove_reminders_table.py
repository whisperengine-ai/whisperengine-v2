"""remove_reminders_table

Revision ID: rm_reminders
Revises: f1x535510n1d
Create Date: 2025-12-07 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'rm_reminders'
down_revision: Union[str, None] = 'f1x535510n1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('v2_reminders')


def downgrade() -> None:
    op.create_table(
        'v2_reminders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('channel_id', sa.String(), nullable=False),
        sa.Column('character_name', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('deliver_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Index for fast polling
    op.create_index(
        'idx_v2_reminders_polling',
        'v2_reminders',
        ['status', 'deliver_at', 'character_name']
    )
