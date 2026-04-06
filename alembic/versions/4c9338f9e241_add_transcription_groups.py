"""add_transcription_groups

Revision ID: 4c9338f9e241
Revises: 3fc7ff0f5b48
Create Date: 2026-04-01 18:00:02.359071

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4c9338f9e241'
down_revision: Union[str, Sequence[str], None] = '3fc7ff0f5b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create transcription_groups table
    op.create_table('transcription_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('custom_instructions', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Add group_id FK to transcriptions
    op.add_column('transcriptions', sa.Column('group_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_transcriptions_group_id', 'transcriptions', 'transcription_groups', ['group_id'], ['id'])

    # Seed default group
    op.execute("INSERT INTO transcription_groups (name, is_default, sort_order) VALUES ('ทั่วไป', true, 0)")


def downgrade() -> None:
    op.drop_constraint('fk_transcriptions_group_id', 'transcriptions', type_='foreignkey')
    op.drop_column('transcriptions', 'group_id')
    op.drop_table('transcription_groups')
