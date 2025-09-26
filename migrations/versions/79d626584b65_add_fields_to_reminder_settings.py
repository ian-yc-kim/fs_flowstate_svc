"""add_fields_to_reminder_settings

Revision ID: 79d626584b65
Revises: 1778d69cdf8c
Create Date: 2024-12-19 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

# revision identifiers, used by Alembic.
revision: str = '79d626584b65'
down_revision: Union[str, None] = '1778d69cdf8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to reminder_settings table
    op.add_column('reminder_settings', sa.Column('status', sa.String(), nullable=False, server_default='pending'))
    op.add_column('reminder_settings', sa.Column('notification_method', sa.String(), nullable=False, server_default='in-app'))
    op.add_column('reminder_settings', sa.Column('delivery_attempted_at', sa.DateTime(), nullable=True))
    op.add_column('reminder_settings', sa.Column('delivery_succeeded_at', sa.DateTime(), nullable=True))
    op.add_column('reminder_settings', sa.Column('failure_reason', sa.Text(), nullable=True))
    
    # Add reminder_metadata column with proper JSON type handling
    # Use JSONB for PostgreSQL, JSON for others (SQLite)
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.add_column('reminder_settings', sa.Column('reminder_metadata', JSONB(), nullable=True))
    else:
        op.add_column('reminder_settings', sa.Column('reminder_metadata', JSON(), nullable=True))
    
    # Create index on status column
    op.create_index('ix_reminder_settings_status', 'reminder_settings', ['status'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_reminder_settings_status', table_name='reminder_settings')
    
    # Drop columns in reverse order
    op.drop_column('reminder_settings', 'reminder_metadata')
    op.drop_column('reminder_settings', 'failure_reason')
    op.drop_column('reminder_settings', 'delivery_succeeded_at')
    op.drop_column('reminder_settings', 'delivery_attempted_at')
    op.drop_column('reminder_settings', 'notification_method')
    op.drop_column('reminder_settings', 'status')
