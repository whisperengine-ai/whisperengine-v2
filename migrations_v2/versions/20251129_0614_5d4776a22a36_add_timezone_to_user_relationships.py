"""add_timezone_to_user_relationships

Revision ID: 5d4776a22a36
Revises: 402d4d5b2a54
Create Date: 2025-11-29 06:14:55.446688+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d4776a22a36'
down_revision: Union[str, None] = '402d4d5b2a54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add timezone columns to v2_user_relationships
    op.add_column('v2_user_relationships', sa.Column('timezone', sa.String(50), nullable=True))
    op.add_column('v2_user_relationships', sa.Column('timezone_confidence', sa.Float(), server_default='0.0', nullable=False))
    op.add_column('v2_user_relationships', sa.Column('quiet_hours_start', sa.Integer(), server_default='22', nullable=False))
    op.add_column('v2_user_relationships', sa.Column('quiet_hours_end', sa.Integer(), server_default='8', nullable=False))


def downgrade() -> None:
    op.drop_column('v2_user_relationships', 'timezone')
    op.drop_column('v2_user_relationships', 'timezone_confidence')
    op.drop_column('v2_user_relationships', 'quiet_hours_start')
    op.drop_column('v2_user_relationships', 'quiet_hours_end')
