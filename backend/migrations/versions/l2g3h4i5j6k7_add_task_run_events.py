"""add task_run_events

Revision ID: l2g3h4i5j6k7
Revises: k1f2a3b4c5d6
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'l2g3h4i5j6k7'
down_revision = 'k1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'task_run_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('task_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('level', sa.String(20), nullable=False, server_default='info'),
        sa.Column('step', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('elapsed_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_task_run_events_run_id', 'task_run_events', ['run_id'])


def downgrade() -> None:
    op.drop_index('ix_task_run_events_run_id', table_name='task_run_events')
    op.drop_table('task_run_events')
