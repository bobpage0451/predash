"""create topics table and add topic_id FK to email_stories

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMS = 768


def upgrade() -> None:
    # --- topics table ---
    op.execute(
        f"""
        CREATE TABLE topics (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            label       TEXT,
            centroid_embedding  vector({EMBEDDING_DIMS}) NOT NULL,
            story_count INT  NOT NULL DEFAULT 0,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_story_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status      TEXT NOT NULL DEFAULT 'active',
            meta        JSONB
        )
        """
    )

    # HNSW index for cosine similarity lookups
    op.execute(
        "CREATE INDEX ix_topics_centroid_embedding "
        "ON topics USING hnsw (centroid_embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_topics_last_story_at ON topics (last_story_at)")
    op.execute("CREATE INDEX ix_topics_story_count   ON topics (story_count)")

    # --- topic_id FK on email_stories ---
    op.execute(
        "ALTER TABLE email_stories "
        "ADD COLUMN topic_id UUID REFERENCES topics(id)"
    )
    op.execute("CREATE INDEX ix_email_stories_topic_id ON email_stories (topic_id)")
    op.execute(
        "CREATE INDEX ix_email_stories_topic_processed "
        "ON email_stories (topic_id, processed_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_email_stories_topic_processed")
    op.execute("DROP INDEX IF EXISTS ix_email_stories_topic_id")
    op.execute("ALTER TABLE email_stories DROP COLUMN IF EXISTS topic_id")
    op.execute("DROP INDEX IF EXISTS ix_topics_story_count")
    op.execute("DROP INDEX IF EXISTS ix_topics_last_story_at")
    op.execute("DROP INDEX IF EXISTS ix_topics_centroid_embedding")
    op.execute("DROP TABLE IF EXISTS topics")
