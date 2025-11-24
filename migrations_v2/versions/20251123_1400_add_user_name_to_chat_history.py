"""add_user_name_to_chat_history

Revision ID: add_user_name_v1
Revises: 368c9b120274
Create Date: 2025-11-23 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_name_v1'
down_revision: Union[str, None] = '368c9b120274'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column
    op.add_column('v2_chat_history', 
                  sa.Column('user_name', sa.Text(), nullable=True))
    
    # Backfill existing records
    op.execute("""
        UPDATE v2_chat_history 
        SET user_name = 'User' 
        WHERE user_name IS NULL AND role = 'human'
    """)


def downgrade() -> None:
    op.drop_column('v2_chat_history', 'user_name')
