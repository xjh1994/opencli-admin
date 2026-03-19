"""add browser_instances table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'browser_instances',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False, server_default='bridge'),
        sa.Column('label', sa.String(100), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint', name='uq_browser_instances_endpoint'),
    )


def downgrade() -> None:
    op.drop_table('browser_instances')
