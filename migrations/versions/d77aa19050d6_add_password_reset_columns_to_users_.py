"""Add password reset columns to users table

Revision ID: d77aa19050d6
Revises: 286e24990b8e
Create Date: 2025-09-26 08:10:41.972831

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd77aa19050d6'
down_revision: Union[str, None] = '286e24990b8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands manually edited to only add new columns ###
    # Add password reset columns to users table
    op.add_column('users', sa.Column('password_reset_token', sa.String(), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires_at', sa.DateTime(), nullable=True))
    
    # Create unique constraint on password_reset_token
    # Use partial unique index for SQLite compatibility (only create unique constraint on non-null values)
    op.create_index(
        'ix_users_password_reset_token_unique',
        'users',
        ['password_reset_token'],
        unique=True,
        sqlite_where=sa.text('password_reset_token IS NOT NULL')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands manually edited ###
    # Drop the unique index
    op.drop_index('ix_users_password_reset_token_unique', table_name='users')
    
    # Drop password reset columns
    op.drop_column('users', 'password_reset_expires_at')
    op.drop_column('users', 'password_reset_token')
    # ### end Alembic commands ###