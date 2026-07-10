"""add email_domains to organizations (resolve tenant from login email domain)

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5f6a7
Create Date: 2026-06-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3c4d5e6a7b8'
down_revision: Union[str, Sequence[str], None] = 'e2b3c4d5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # JSON list of email domains that map to this tenant, e.g. ["doh.go.th"].
    op.add_column('organizations', sa.Column('email_domains', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('organizations', 'email_domains')
