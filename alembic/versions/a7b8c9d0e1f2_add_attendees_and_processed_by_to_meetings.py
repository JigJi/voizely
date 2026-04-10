"""Add attendees and processed_by to meeting_recordings

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('meeting_recordings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attendees', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('processed_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_meeting_recordings_processed_by', 'users', ['processed_by'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('meeting_recordings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_meeting_recordings_processed_by', type_='foreignkey')
        batch_op.drop_column('processed_by')
        batch_op.drop_column('attendees')
