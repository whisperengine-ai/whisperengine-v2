"""add_character_profiles

Revision ID: 20251126_1200
Revises: 20251125_2300_add_universe_privacy
Create Date: 2025-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_character_profiles'
down_revision: Union[str, None] = 'add_universe_privacy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create character_profiles table
    op.create_table(
        'character_profiles',
        sa.Column('character_name', sa.Text(), nullable=False),
        sa.Column('visual_description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('character_name')
    )


def downgrade() -> None:
    op.drop_table('character_profiles')
