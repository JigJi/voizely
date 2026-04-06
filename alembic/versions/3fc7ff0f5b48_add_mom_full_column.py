"""Add mom_full column

Revision ID: 3fc7ff0f5b48
Revises: e8917775e337
Create Date: 2026-03-28 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3fc7ff0f5b48'
down_revision: Union[str, Sequence[str], None] = 'e8917775e337'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mom_full', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.drop_column('mom_full')
