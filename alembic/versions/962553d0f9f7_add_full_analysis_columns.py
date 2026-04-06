"""Add full analysis columns

Revision ID: 962553d0f9f7
Revises: 09ebda891976
Create Date: 2026-03-28 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '962553d0f9f7'
down_revision: Union[str, Sequence[str], None] = '09ebda891976'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auto_title', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('summary_short', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('topics', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('action_items', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('key_decisions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('open_questions', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.drop_column('open_questions')
        batch_op.drop_column('key_decisions')
        batch_op.drop_column('action_items')
        batch_op.drop_column('topics')
        batch_op.drop_column('summary_short')
        batch_op.drop_column('auto_title')
