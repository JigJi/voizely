"""Add source column to speaker_profiles

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('speaker_profiles', sa.Column('source', sa.String(20), server_default='manual', nullable=False))


def downgrade() -> None:
    op.drop_column('speaker_profiles', 'source')
