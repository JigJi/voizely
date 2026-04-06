"""Add deepgram_confidence column

Revision ID: 12ef8b127b1f
Revises: d33924b109b2
Create Date: 2026-03-28 16:39:25.517613

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '12ef8b127b1f'
down_revision: Union[str, Sequence[str], None] = 'd33924b109b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deepgram_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('transcriptions', schema=None) as batch_op:
        batch_op.drop_column('deepgram_confidence')
