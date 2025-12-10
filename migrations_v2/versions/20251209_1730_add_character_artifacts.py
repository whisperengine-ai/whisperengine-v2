"""add_character_artifacts table for Daily Life Graph

Tracks when character artifacts (diary, dream, goal_review) were created
for staleness detection in the Daily Life Graph (Phase E31).

Revision ID: e31_artifacts
Revises: rm_reminders
Create Date: 2025-12-09 17:30:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e31_artifacts'
down_revision: Union[str, None] = 'rm_reminders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'character_artifacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('character_name', sa.String(length=64), nullable=False),
        sa.Column('artifact_type', sa.String(length=32), nullable=False),  # diary, dream, goal_review
        sa.Column('artifact_id', sa.String(length=64), nullable=True),  # Qdrant point ID or external ref
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),  # Optional extra data
        sa.PrimaryKeyConstraint('id')
    )
    
    # Index for fast lookups by character + type
    op.create_index(
        'ix_character_artifacts_char_type',
        'character_artifacts',
        ['character_name', 'artifact_type']
    )
    
    # Index for ordering by creation time
    op.create_index(
        'ix_character_artifacts_created',
        'character_artifacts',
        ['created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_character_artifacts_created', table_name='character_artifacts')
    op.drop_index('ix_character_artifacts_char_type', table_name='character_artifacts')
    op.drop_table('character_artifacts')
