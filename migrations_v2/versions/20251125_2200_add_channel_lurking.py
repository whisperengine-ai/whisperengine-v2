"""Add channel lurking tables

Revision ID: add_lurk_tables
Revises: add_evolution_cols
Create Date: 2025-11-25 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_lurk_tables'
down_revision = 'add_evolution_cols'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create v2_channel_settings table for per-channel lurk configuration
    op.create_table(
        'v2_channel_settings',
        sa.Column('channel_id', sa.String(64), primary_key=True),
        sa.Column('guild_id', sa.String(64), nullable=False),
        sa.Column('lurk_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('lurk_threshold', sa.Float(), default=0.7, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    )
    
    # Create index on guild_id for faster lookups
    op.create_index('ix_v2_channel_settings_guild_id', 'v2_channel_settings', ['guild_id'])
    
    # Create v2_lurk_responses table for analytics
    op.create_table(
        'v2_lurk_responses',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('channel_id', sa.String(64), nullable=False),
        sa.Column('guild_id', sa.String(64), nullable=True),
        sa.Column('user_id', sa.String(64), nullable=False),
        sa.Column('character_name', sa.String(64), nullable=False),
        sa.Column('trigger_message', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('detected_topics', sa.JSON(), nullable=True),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )
    
    # Create indexes for analytics queries
    op.create_index('ix_v2_lurk_responses_channel_id', 'v2_lurk_responses', ['channel_id'])
    op.create_index('ix_v2_lurk_responses_character_name', 'v2_lurk_responses', ['character_name'])
    op.create_index('ix_v2_lurk_responses_created_at', 'v2_lurk_responses', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_v2_lurk_responses_created_at', 'v2_lurk_responses')
    op.drop_index('ix_v2_lurk_responses_character_name', 'v2_lurk_responses')
    op.drop_index('ix_v2_lurk_responses_channel_id', 'v2_lurk_responses')
    op.drop_table('v2_lurk_responses')
    
    op.drop_index('ix_v2_channel_settings_guild_id', 'v2_channel_settings')
    op.drop_table('v2_channel_settings')
