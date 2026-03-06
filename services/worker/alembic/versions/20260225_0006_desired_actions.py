"""desired_actions, action_matches tables + action_type column on email_stories

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # tables removed — see migration 0008


def downgrade() -> None:
    pass
