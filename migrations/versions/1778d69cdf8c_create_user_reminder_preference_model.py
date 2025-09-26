"""create_user_reminder_preference_model

Revision ID: 1778d69cdf8c
Revises: d9d977559d32
Create Date: 2025-09-26 12:34:50.545612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1778d69cdf8c'
down_revision: Union[str, None] = 'd9d977559d32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_reminder_preferences table
    op.create_table('user_reminder_preferences',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('event_category', sa.String(), nullable=False),
    sa.Column('preparation_time_minutes', sa.Integer(), nullable=False),
    sa.Column('is_custom', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'event_category', name='uq_user_event_category')
    )
    op.create_index(op.f('ix_user_reminder_preferences_user_id'), 'user_reminder_preferences', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop user_reminder_preferences table
    op.drop_index(op.f('ix_user_reminder_preferences_user_id'), table_name='user_reminder_preferences')
    op.drop_table('user_reminder_preferences')
