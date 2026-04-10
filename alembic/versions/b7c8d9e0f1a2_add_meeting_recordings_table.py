"""Add meeting_recordings table

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('meeting_recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=20), nullable=False),
        sa.Column('platform_recording_id', sa.String(length=500), nullable=False),
        sa.Column('platform_meeting_id', sa.String(length=500), nullable=True),
        sa.Column('meeting_subject', sa.String(length=500), nullable=True),
        sa.Column('meeting_organizer', sa.String(length=200), nullable=True),
        sa.Column('meeting_start_time', sa.DateTime(), nullable=True),
        sa.Column('meeting_end_time', sa.DateTime(), nullable=True),
        sa.Column('recording_url', sa.Text(), nullable=True),
        sa.Column('audio_file_id', sa.Integer(), nullable=True),
        sa.Column('transcription_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('discovered_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('platform_metadata', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['audio_file_id'], ['audio_files.id']),
        sa.ForeignKeyConstraint(['transcription_id'], ['transcriptions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform', 'platform_recording_id', name='uq_platform_recording'),
    )
    with op.batch_alter_table('meeting_recordings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_meeting_recordings_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_meeting_recordings_platform'), ['platform'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('meeting_recordings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_meeting_recordings_platform'))
        batch_op.drop_index(batch_op.f('ix_meeting_recordings_id'))
    op.drop_table('meeting_recordings')
