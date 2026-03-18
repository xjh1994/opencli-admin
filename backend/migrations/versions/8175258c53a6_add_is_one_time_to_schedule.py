"""add_is_one_time_to_schedule

Revision ID: 8175258c53a6
Revises: c6ccac131b3d
Create Date: 2026-03-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '8175258c53a6'
down_revision: Union[str, None] = 'c6ccac131b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cron_schedules', sa.Column('is_one_time', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('cron_schedules', 'is_one_time')
