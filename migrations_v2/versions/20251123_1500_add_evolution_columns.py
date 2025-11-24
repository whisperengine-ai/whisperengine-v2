"""add_evolution_columns

Revision ID: add_evolution_cols
Revises: add_user_name_v1
Create Date: 2025-11-23 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_evolution_cols'
down_revision: Union[str, None] = 'add_user_name_v1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to v2_user_relationships
    op.add_column('v2_user_relationships', sa.Column('evolution_stage', sa.Text(), server_default='Stranger', nullable=False))
    op.add_column('v2_user_relationships', sa.Column('mood', sa.Text(), server_default='neutral', nullable=True))
    op.add_column('v2_user_relationships', sa.Column('mood_intensity', sa.Float(), server_default='0.5', nullable=True))
    op.add_column('v2_user_relationships', sa.Column('relationship_summary', sa.Text(), nullable=True))
    op.add_column('v2_user_relationships', sa.Column('last_milestone_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('v2_user_relationships', 'evolution_stage')
    op.drop_column('v2_user_relationships', 'mood')
    op.drop_column('v2_user_relationships', 'mood_intensity')
    op.drop_column('v2_user_relationships', 'relationship_summary')
    op.drop_column('v2_user_relationships', 'last_milestone_date')
