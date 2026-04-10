"""Add user_id to transcription_groups

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('transcription_groups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_groups_user_id', 'users', ['user_id'], ['id'])
        batch_op.create_index('ix_transcription_groups_user_id', ['user_id'])

    # Assign existing groups to admin (user_id=1)
    op.execute("UPDATE transcription_groups SET user_id = 1 WHERE user_id IS NULL")


def downgrade() -> None:
    with op.batch_alter_table('transcription_groups', schema=None) as batch_op:
        batch_op.drop_index('ix_transcription_groups_user_id')
        batch_op.drop_constraint('fk_groups_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')
