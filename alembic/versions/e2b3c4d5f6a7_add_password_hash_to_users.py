"""add password_hash to users (local accounts for non-AD tenants)

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2b3c4d5f6a7'
down_revision: Union[str, Sequence[str], None] = 'd1a2b3c4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'password_hash')
