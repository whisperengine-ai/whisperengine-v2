"""Add universe privacy settings

Revision ID: add_universe_privacy
Revises: add_lurk_tables
Create Date: 2025-11-25 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_universe_privacy'
down_revision = 'add_lurk_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'v2_user_privacy_settings',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('share_with_other_bots', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('share_across_planets', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('allow_bot_introductions', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('invisible_mode', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('v2_user_privacy_settings')
