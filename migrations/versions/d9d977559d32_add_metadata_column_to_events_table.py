"""add metadata column to events table

Revision ID: d9d977559d32
Revises: d77aa19050d6
Create Date: 2025-09-26 09:34:35.483642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from fs_flowstate_svc.models.flowstate_models import CrossDBJSON


# revision identifiers, used by Alembic.
revision: str = 'd9d977559d32'
down_revision: Union[str, None] = 'd77aa19050d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add metadata column to events table
    op.add_column('events', sa.Column('metadata', CrossDBJSON(), nullable=True))


def downgrade() -> None:
    # Remove metadata column from events table
    op.drop_column('events', 'metadata')
