"""add sentiment, named_entities, emojis to email_stories

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_stories",
        sa.Column("sentiment", sa.Text(), nullable=True),
    )
    op.add_column(
        "email_stories",
        sa.Column("named_entities", JSONB(), nullable=True),
    )
    op.add_column(
        "email_stories",
        sa.Column("emojis", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_stories", "emojis")
    op.drop_column("email_stories", "named_entities")
    op.drop_column("email_stories", "sentiment")
