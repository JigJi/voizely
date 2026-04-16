"""add is_active to speaker_profiles

Revision ID: 8bcf9a2e4d11
Revises: 7abcbf5b5bfd
Create Date: 2026-04-16 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8bcf9a2e4d11'
down_revision: Union[str, Sequence[str], None] = '7abcbf5b5bfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'speaker_profiles',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('speaker_profiles', 'is_active')
