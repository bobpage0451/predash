"""initial schema – emails_raw and emails_processed

Revision ID: 0001
Revises: None
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # emails_raw
    # ------------------------------------------------------------------
    op.create_table(
        "emails_raw",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("mailbox", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=True),
        sa.Column("imap_uid", sa.BigInteger(), nullable=True),
        sa.Column("from_addr", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("date_sent", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_received", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("raw_headers", JSONB(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Partial unique indexes
    op.execute(
        "CREATE UNIQUE INDEX uq_emails_raw_source_message_id "
        "ON emails_raw (source, message_id) "
        "WHERE message_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_emails_raw_source_mailbox_imap_uid "
        "ON emails_raw (source, mailbox, imap_uid) "
        "WHERE imap_uid IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_emails_raw_source_sha256 "
        "ON emails_raw (source, sha256) "
        "WHERE sha256 IS NOT NULL"
    )

    # Standard indexes
    op.create_index("ix_emails_raw_date_received", "emails_raw", ["date_received"])
    op.create_index("ix_emails_raw_ingested_at", "emails_raw", ["ingested_at"])

    # ------------------------------------------------------------------
    # emails_processed
    # ------------------------------------------------------------------
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

    # Unique constraint: prevent duplicate runs
    op.create_index(
        "uq_emails_processed_run",
        "emails_processed",
        ["email_id", "processor", "model", "prompt_version"],
        unique=True,
    )

    # Standard indexes
    op.create_index("ix_emails_processed_processed_at", "emails_processed", ["processed_at"])
    op.create_index("ix_emails_processed_email_id", "emails_processed", ["email_id"])


def downgrade() -> None:
    op.drop_table("emails_processed")
    op.drop_table("emails_raw")
