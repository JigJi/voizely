"""add user_id to speaker_profiles

Revision ID: caad2a2c5ca0
Revises: 8bcf9a2e4d11
Create Date: 2026-04-17 16:02:36.368560

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'caad2a2c5ca0'
down_revision: Union[str, Sequence[str], None] = '8bcf9a2e4d11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('speaker_profiles', sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('speaker_profiles', 'user_id')
