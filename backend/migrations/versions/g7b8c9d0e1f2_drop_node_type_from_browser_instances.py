"""drop node_type from browser_instances

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-20 02:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('browser_instances', 'node_type')


def downgrade() -> None:
    op.add_column(
        'browser_instances',
        sa.Column('node_type', sa.String(20), nullable=False, server_default='local'),
    )
