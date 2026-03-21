"""add node_type to edge_nodes

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'k1f2a3b4c5d6'
down_revision = 'j0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('edge_nodes', sa.Column('node_type', sa.String(20), nullable=False, server_default='docker'))


def downgrade() -> None:
    op.drop_column('edge_nodes', 'node_type')
