"""add user_calendar_cache table

Revision ID: 7abcbf5b5bfd
Revises: c9d0e1f2a3b4
Create Date: 2026-04-16 10:25:56.105859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7abcbf5b5bfd'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_calendar_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('event_start', sa.DateTime(), nullable=True),
        sa.Column('cached_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'subject', 'event_start', name='uq_user_calendar_event')
    )
    op.create_index('ix_user_calendar_cache_user_id', 'user_calendar_cache', ['user_id'])
    op.create_index('ix_user_calendar_cache_cached_date', 'user_calendar_cache', ['cached_date'])


def downgrade() -> None:
    op.drop_table('user_calendar_cache')
