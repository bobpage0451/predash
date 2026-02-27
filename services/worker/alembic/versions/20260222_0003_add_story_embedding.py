"""add embedding column to email_stories

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match the embedding model output dimensions (nomic-embed-text = 768)
EMBEDDING_DIMS = 768


def upgrade() -> None:
    # Enable the pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add the nullable embedding column
    op.execute(
        f"ALTER TABLE email_stories ADD COLUMN embedding vector({EMBEDDING_DIMS})"
    )

    # HNSW index for cosine similarity — works well at any dataset size
    op.execute(
        "CREATE INDEX ix_email_stories_embedding "
        "ON email_stories USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_email_stories_embedding")
    op.execute("ALTER TABLE email_stories DROP COLUMN IF EXISTS embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
