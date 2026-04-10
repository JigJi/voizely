"""Add user_id to correction_dict

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-08 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('correction_dict', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_corrections_user_id', 'users', ['user_id'], ['id'])
        batch_op.create_index('ix_correction_dict_user_id', ['user_id'])
        # Drop old unique on 'wrong' alone, replace with composite unique per user
        batch_op.drop_constraint('correction_dict_wrong_key', type_='unique')
        batch_op.create_unique_constraint('uq_correction_user_wrong', ['user_id', 'wrong'])

    # Assign existing corrections to admin (user_id=1)
    op.execute("UPDATE correction_dict SET user_id = 1 WHERE user_id IS NULL")


def downgrade() -> None:
    with op.batch_alter_table('correction_dict', schema=None) as batch_op:
        batch_op.drop_constraint('uq_correction_user_wrong', type_='unique')
        batch_op.create_unique_constraint('correction_dict_wrong_key', ['wrong'])
        batch_op.drop_index('ix_correction_dict_user_id')
        batch_op.drop_constraint('fk_corrections_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')
