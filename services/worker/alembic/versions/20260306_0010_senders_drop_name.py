"""Drop name column from senders table

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("senders", "name")


def downgrade() -> None:
    op.add_column("senders", sa.Column("name", sa.Text(), nullable=True))
