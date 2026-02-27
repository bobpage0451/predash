"""drop emails_processed table

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("emails_processed")


def downgrade() -> None:
    # Recreate the table for rollback
    op.create_table(
        "emails_processed",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email_id", UUID(as_uuid=True), sa.ForeignKey("emails_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("processor", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ok'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "uq_emails_processed_run",
        "emails_processed",
        ["email_id", "processor", "model", "prompt_version"],
        unique=True,
    )
    op.create_index("ix_emails_processed_processed_at", "emails_processed", ["processed_at"])
    op.create_index("ix_emails_processed_email_id", "emails_processed", ["email_id"])
