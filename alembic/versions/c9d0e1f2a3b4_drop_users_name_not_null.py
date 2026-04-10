"""Drop NOT NULL constraint on users.name (legacy column not in model)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users.name is a legacy column not present in SQLAlchemy model.
    # Drop NOT NULL so insert via ORM works without explicit name value.
    op.alter_column('users', 'name', nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'name', nullable=False)
