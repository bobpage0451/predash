"""add email_stories table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_stories",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email_id", UUID(as_uuid=True), sa.ForeignKey("emails_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("story_index", sa.Integer(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("processor", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ok'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Unique constraint: prevent duplicate stories per run
    op.create_index(
        "uq_email_stories_run",
        "email_stories",
        ["email_id", "processor", "model", "prompt_version", "story_index"],
        unique=True,
    )

    # Standard indexes
    op.create_index("ix_email_stories_processed_at", "email_stories", ["processed_at"])
    op.create_index("ix_email_stories_email_id", "email_stories", ["email_id"])


def downgrade() -> None:
    op.drop_table("email_stories")
