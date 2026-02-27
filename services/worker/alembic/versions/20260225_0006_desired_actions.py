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
    # --- Add action_type column to email_stories ---
    op.add_column(
        "email_stories",
        sa.Column("action_type", sa.Text(), nullable=True),
    )

    # --- desired_actions table ---
    op.create_table(
        "desired_actions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("action_types", JSONB(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- action_matches table ---
    op.create_table(
        "action_matches",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "desired_action_id",
            UUID(as_uuid=True),
            sa.ForeignKey("desired_actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "story_id",
            UUID(as_uuid=True),
            sa.ForeignKey("email_stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("action_type_matched", sa.Boolean(), nullable=True),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for action_matches
    op.create_index(
        "uq_action_matches_action_story",
        "action_matches",
        ["desired_action_id", "story_id"],
        unique=True,
    )
    op.create_index(
        "ix_action_matches_desired_action_id",
        "action_matches",
        ["desired_action_id"],
    )
    op.create_index(
        "ix_action_matches_story_id",
        "action_matches",
        ["story_id"],
    )
    op.create_index(
        "ix_action_matches_matched_at",
        "action_matches",
        ["matched_at"],
    )


def downgrade() -> None:
    op.drop_table("action_matches")
    op.drop_table("desired_actions")
    op.drop_column("email_stories", "action_type")
