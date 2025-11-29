"""Add TTL and user-specific fields to goals

Revision ID: 20251129_0200
Revises: 
Create Date: 2025-11-29

Adds:
- expires_at: Optional expiry timestamp for goals (NULL = no expiry)
- target_user_id: For user-specific goals (inferred, user-requested)
- requested_by_user: Boolean flag for user-requested goals

TTL defaults by source:
- core: No expiry (NULL)
- strategic: 30 days (community trends change)
- inferred: 14 days (patterns may shift)  
- user: 7 days (short-term requests) - can be extended
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251129_0200'
down_revision = 'e50000000001'  # add_reminders_table
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add expires_at column (nullable - NULL means no expiry)
    op.add_column('v2_goals', sa.Column('expires_at', sa.DateTime(), nullable=True))
    
    # Add target_user_id for user-specific goals
    op.add_column('v2_goals', sa.Column('target_user_id', sa.String(length=255), nullable=True))
    
    # Add index for efficient expiry queries
    op.create_index('ix_v2_goals_expires_at', 'v2_goals', ['expires_at'], unique=False)
    
    # Add index for user-specific goal lookups
    op.create_index('ix_v2_goals_target_user', 'v2_goals', ['character_name', 'target_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_v2_goals_target_user', table_name='v2_goals')
    op.drop_index('ix_v2_goals_expires_at', table_name='v2_goals')
    op.drop_column('v2_goals', 'target_user_id')
    op.drop_column('v2_goals', 'expires_at')
