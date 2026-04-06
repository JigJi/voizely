"""Add analysis columns

Revision ID: 09ebda891976
Revises: 12ef8b127b1f
Create Date: 2026-03-28 16:58:43.724522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '09ebda891976'
down_revision: Union[str, Sequence[str], None] = '12ef8b127b1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sentiment', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('meeting_tone', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('meeting_type', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.drop_column('meeting_type')
        batch_op.drop_column('meeting_tone')
        batch_op.drop_column('sentiment')
