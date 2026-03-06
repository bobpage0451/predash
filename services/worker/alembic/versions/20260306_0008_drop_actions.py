"""Drop desired_actions, action_matches tables and action_type column

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop action_matches first (FK → desired_actions and email_stories)
    op.drop_table("action_matches")
    # Drop desired_actions
    op.drop_table("desired_actions")
    # Drop action_type column from email_stories
    op.drop_column("email_stories", "action_type")


def downgrade() -> None:
    # Recreate action_type column
    op.add_column(
        "email_stories",
        sa.Column("action_type", sa.Text(), nullable=True),
    )

    # Recreate desired_actions table
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

    # Recreate action_matches table
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

    # Recreate indexes
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
