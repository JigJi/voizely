"""alter users table for auth

Revision ID: a1b2c3d4e5f6
Revises: 4c9338f9e241
Create Date: 2026-04-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4c9338f9e241'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns
    op.add_column('users', sa.Column('username', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('first_name', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('department', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(), nullable=True))

    # Populate username from name for existing rows
    op.execute("UPDATE users SET username = LOWER(REPLACE(name, ' ', '_')) WHERE username IS NULL")

    # Make username not null + unique
    op.alter_column('users', 'username', nullable=False)
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
    op.create_index('ix_users_username', 'users', ['username'])

    # Expand role column
    op.alter_column('users', 'role', type_=sa.String(20), server_default='USER')

    # Make email nullable
    op.alter_column('users', 'email', nullable=True)


def downgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'department')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'username')
    op.alter_column('users', 'role', type_=sa.String(5))
    op.alter_column('users', 'email', nullable=False)
