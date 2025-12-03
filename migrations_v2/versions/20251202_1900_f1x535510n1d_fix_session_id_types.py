"""fix_session_id_types

Revision ID: f1x535510n1d
Revises: e50000000001
Create Date: 2025-12-02 19:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1x535510n1d'
down_revision: Union[str, None] = ('e50000000001', '20251129_0200')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the foreign key constraint on v2_summaries
    op.drop_constraint('v2_summaries_session_id_fkey', 'v2_summaries', type_='foreignkey')

    # 2. Alter v2_summaries.session_id to String
    # We need to cast existing UUIDs to String
    op.alter_column('v2_summaries', 'session_id',
               existing_type=postgresql.UUID(),
               type_=sa.String(),
               postgresql_using='session_id::text',
               nullable=False)

    # 3. Alter v2_conversation_sessions.id to String
    op.alter_column('v2_conversation_sessions', 'id',
               existing_type=postgresql.UUID(),
               type_=sa.String(),
               postgresql_using='id::text',
               nullable=False)
               
    # We do NOT re-add the foreign key constraint because session_id in summaries
    # might refer to cross-bot sessions or other types that don't exist in v2_conversation_sessions
    # which is primarily for 1-on-1 user-bot sessions.


def downgrade() -> None:
    # 1. Revert v2_conversation_sessions.id to UUID
    # This might fail if there are non-UUID strings. 
    # We assume for downgrade that we haven't inserted invalid UUIDs yet or we accept failure.
    op.alter_column('v2_conversation_sessions', 'id',
               existing_type=sa.String(),
               type_=postgresql.UUID(),
               postgresql_using='id::uuid',
               nullable=False)

    # 2. Revert v2_summaries.session_id to UUID
    op.alter_column('v2_summaries', 'session_id',
               existing_type=sa.String(),
               type_=postgresql.UUID(),
               postgresql_using='session_id::uuid',
               nullable=False)

    # 3. Re-add foreign key
    op.create_foreign_key(
        'v2_summaries_session_id_fkey',
        'v2_summaries', 'v2_conversation_sessions',
        ['session_id'], ['id']
    )
