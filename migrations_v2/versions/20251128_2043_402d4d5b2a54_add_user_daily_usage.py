"""add_user_daily_usage

Revision ID: 402d4d5b2a54
Revises: add_goal_src_prio_strat
Create Date: 2025-11-28 20:43:37.925817+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '402d4d5b2a54'
down_revision: Union[str, None] = 'add_goal_src_prio_strat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'v2_user_daily_usage',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('image_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('audio_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'date')
    )


def downgrade() -> None:
    op.drop_table('v2_user_daily_usage')
