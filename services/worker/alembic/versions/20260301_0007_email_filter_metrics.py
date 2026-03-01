"""email_filter_metrics table for pre-LLM filtering pipeline

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_filter_metrics",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "email_id",
            UUID(as_uuid=True),
            sa.ForeignKey("emails_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Final scores
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("quality", sa.Text(), nullable=True),
        sa.Column("filter_outcome", sa.Text(), nullable=False),
        # Raw signals
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("link_density", sa.Float(), nullable=True),
        sa.Column("text_html_ratio", sa.Float(), nullable=True),
        sa.Column("avg_sentence_len", sa.Float(), nullable=True),
        sa.Column("cta_count", sa.Integer(), nullable=True),
        sa.Column("has_list_unsubscribe", sa.Boolean(), nullable=True),
        sa.Column("has_bulk_precedence", sa.Boolean(), nullable=True),
        sa.Column("esp_detected", sa.Text(), nullable=True),
    )

    # One evaluation per email (can be deleted and re-evaluated on threshold changes)
    op.create_index(
        "uq_email_filter_metrics_email_id",
        "email_filter_metrics",
        ["email_id"],
        unique=True,
    )
    op.create_index(
        "ix_email_filter_metrics_filter_outcome",
        "email_filter_metrics",
        ["filter_outcome"],
    )
    op.create_index(
        "ix_email_filter_metrics_evaluated_at",
        "email_filter_metrics",
        ["evaluated_at"],
    )


def downgrade() -> None:
    op.drop_table("email_filter_metrics")
