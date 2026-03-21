"""add node_url to task_runs

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-03-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'j0e1f2a3b4c5'
down_revision: Union[str, None] = 'i9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task_runs', sa.Column('node_url', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('task_runs', 'node_url')
