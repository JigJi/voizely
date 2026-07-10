"""add multi-tenancy: organizations table + tenant_id on all owned tables

Revision ID: d1a2b3c4e5f6
Revises: caad2a2c5ca0
Create Date: 2026-06-12

Phase 0 of multi-tenant rollout. Creates the organizations (tenant) table, seeds
tenant_id=1 = the existing/legacy organization, and adds a tenant_id FK to every
table that holds tenant-owned data. All pre-existing rows are back-filled to
tenant_id=1 via the column's server_default.

NOTE: server_default='1' is intentional and TRANSITIONAL. It keeps the live
single-tenant app working (every insert lands in tenant 1) until the JWT/middleware
layer is wired up to set tenant_id explicitly. A later migration should drop the
server_default once middleware enforces it, so bugs can't silently leak into tenant 1.

transcription_segments intentionally has NO tenant_id — it derives its tenant via
transcription_id (avoids back-filling the largest table).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, Sequence[str], None] = 'caad2a2c5ca0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that get a tenant_id FK. transcription_segments is excluded by design.
TENANT_TABLES = [
    "users",
    "audio_files",
    "transcriptions",
    "transcription_groups",
    "speaker_profiles",
    "correction_dict",
    "meeting_recordings",
    "user_calendar_cache",
]


def upgrade() -> None:
    # 1. organizations (tenant) table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pipeline_mode", sa.String(length=20), nullable=False, server_default="cloud"),
        sa.Column("ad_config", sa.JSON(), nullable=True),
        sa.Column("branding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # 2. Seed legacy tenant (id=1). ad_config NULL → app falls back to global AD_* env settings.
    op.execute(
        "INSERT INTO organizations (id, name, slug, is_active, pipeline_mode) "
        "VALUES (1, 'Default Organization', 'default', true, 'cloud')"
    )
    # Keep the serial sequence ahead of the explicit id=1 insert so the next org gets id=2.
    op.execute("SELECT setval(pg_get_serial_sequence('organizations', 'id'), 1, true)")

    # 3. tenant_id FK on every owned table. server_default='1' back-fills existing rows.
    for table in TENANT_TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant", table, "organizations", ["tenant_id"], ["id"]
        )

    # 4. users: make username and email unique *per tenant* instead of globally
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.create_unique_constraint("uq_users_tenant_username", "users", ["tenant_id", "username"])
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])

    # 5. correction_dict: live constraint is unique(user_id, wrong) → add tenant scope
    op.drop_constraint("uq_correction_user_wrong", "correction_dict", type_="unique")
    op.create_unique_constraint(
        "uq_correction_tenant_user_wrong", "correction_dict",
        ["tenant_id", "user_id", "wrong"],
    )


def downgrade() -> None:
    # 5. restore correction_dict unique(user_id, wrong)
    op.drop_constraint("uq_correction_tenant_user_wrong", "correction_dict", type_="unique")
    op.create_unique_constraint("uq_correction_user_wrong", "correction_dict", ["user_id", "wrong"])

    # 4. restore users global uniques
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.drop_constraint("uq_users_tenant_username", "users", type_="unique")
    op.create_unique_constraint("uq_users_username", "users", ["username"])

    # 3. drop tenant_id from every table
    for table in TENANT_TABLES:
        op.drop_constraint(f"fk_{table}_tenant", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    # 1-2. drop organizations
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_index("ix_organizations_id", table_name="organizations")
    op.drop_table("organizations")
