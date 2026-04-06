"""Add correction_dict table

Revision ID: e8917775e337
Revises: 962553d0f9f7
Create Date: 2026-03-28 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e8917775e337'
down_revision: Union[str, Sequence[str], None] = '962553d0f9f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('correction_dict',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wrong', sa.String(length=200), nullable=False),
        sa.Column('correct', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wrong')
    )
    with op.batch_alter_table('correction_dict', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_correction_dict_id'), ['id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('correction_dict', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_correction_dict_id'))
    op.drop_table('correction_dict')
