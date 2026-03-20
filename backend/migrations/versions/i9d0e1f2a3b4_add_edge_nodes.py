"""add edge_nodes and edge_node_events tables

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-03-20 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'i9d0e1f2a3b4'
down_revision: Union[str, None] = 'h8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'edge_nodes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('url', sa.String(512), nullable=False, unique=True),
        sa.Column('label', sa.String(255), nullable=False, server_default=''),
        sa.Column('protocol', sa.String(10), nullable=False, server_default='http'),
        sa.Column('mode', sa.String(20), nullable=False, server_default='bridge'),
        sa.Column('status', sa.String(20), nullable=False, server_default='offline'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'edge_node_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(36),
                  sa.ForeignKey('edge_nodes.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('event', sa.String(50), nullable=False),
        sa.Column('ip', sa.String(45), nullable=True),
        sa.Column('event_meta', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('edge_node_events')
    op.drop_table('edge_nodes')
