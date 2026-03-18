"""add ai_agents table and agent_id fk on tasks/schedules

Revision ID: a1b2c3d4e5f6
Revises: 5a9a94795d00
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5a9a94795d00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_agents',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('processor_type', sa.String(length=50), nullable=False, server_default='claude'),
        sa.Column('model', sa.String(length=255), nullable=True),
        sa.Column('prompt_template', sa.Text(), nullable=False, server_default=''),
        sa.Column('processor_config', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # SQLite does not support ADD COLUMN ... REFERENCES in ALTER TABLE,
    # so we use batch mode which rewrites the table via a temp copy.
    with op.batch_alter_table('collection_tasks') as batch_op:
        batch_op.add_column(
            sa.Column('agent_id', sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_collection_tasks_agent_id',
            'ai_agents',
            ['agent_id'],
            ['id'],
            ondelete='SET NULL',
        )

    with op.batch_alter_table('cron_schedules') as batch_op:
        batch_op.add_column(
            sa.Column('agent_id', sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_cron_schedules_agent_id',
            'ai_agents',
            ['agent_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('cron_schedules') as batch_op:
        batch_op.drop_constraint('fk_cron_schedules_agent_id', type_='foreignkey')
        batch_op.drop_column('agent_id')

    with op.batch_alter_table('collection_tasks') as batch_op:
        batch_op.drop_constraint('fk_collection_tasks_agent_id', type_='foreignkey')
        batch_op.drop_column('agent_id')

    op.drop_table('ai_agents')
