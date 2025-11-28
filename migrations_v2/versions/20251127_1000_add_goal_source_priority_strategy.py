"""add_goal_source_priority_strategy

Revision ID: add_goal_source_priority_strategy
Revises: add_character_profiles
Create Date: 2025-11-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_goal_source_priority_strategy'
down_revision: Union[str, None] = 'add_character_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to v2_goals
    op.add_column('v2_goals', sa.Column('source', sa.String(length=50), server_default='core', nullable=False))
    op.add_column('v2_goals', sa.Column('current_strategy', sa.Text(), nullable=True))
    op.add_column('v2_goals', sa.Column('category', sa.String(length=50), server_default='general', nullable=False))


def downgrade() -> None:
    op.drop_column('v2_goals', 'source')
    op.drop_column('v2_goals', 'current_strategy')
    op.drop_column('v2_goals', 'category')
