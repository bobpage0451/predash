"""One-shot embedding backfill for email_stories.

Reads stories that have no embedding yet, computes an embedding via Ollama's
/api/embed endpoint using the headline + summary, and stores the result.

Usage:
    cd services/worker
    python -m app.llm.compute_embeddings [--limit N] [--batch-size N]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv
from sqlalchemy import select, func

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backfill embeddings for email_stories",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("EMAIL_PROCESS_LIMIT", "0")),
        help="Max stories to process (0 = all). Default: EMAIL_PROCESS_LIMIT or 0",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Commit every N rows (default: 50)",
    )
    p.add_argument(
        "--model",
        type=str,
        default=os.environ.get("EMBEDDING_MODEL", "nomic-embed-text"),
        help="Ollama embedding model name. Default: EMBEDDING_MODEL or nomic-embed-text",
    )
    p.add_argument(
        "--ollama-url",
        type=str,
        default=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434"),
        help="Ollama base URL. Default: OLLAMA_BASE_URL",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds (default: 60)",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Run the one-shot embedding backfill."""
    args = _parse_args(argv)

    # Late imports so --help is fast
    from app.db import get_session
    from app.models import EmailStory
    from app.llm import ollama_client

    Session = get_session()

    log.info(
        "Embedding backfill starting  model=%s  url=%s  limit=%s  batch=%d",
        args.model,
        args.ollama_url,
        args.limit or "unlimited",
        args.batch_size,
    )

    # Build query: stories with status=ok and no embedding yet
    query = (
        select(EmailStory)
        .where(EmailStory.status == "ok")
        .where(EmailStory.embedding.is_(None))
        .order_by(EmailStory.processed_at.asc())
    )
    if args.limit:
        query = query.limit(args.limit)

    with Session() as session:
        stories = session.execute(query).scalars().all()
        total = len(stories)

        if total == 0:
            log.info("No stories without embeddings found. Nothing to do.")
            return

        log.info("Found %d stories to embed", total)

        embedded = 0
        errors = 0
        t0 = time.time()

        for i, story in enumerate(stories, 1):
            input_text = f"{story.headline} — {story.summary}"
            try:
                vector = ollama_client.embed(
                    base_url=args.ollama_url,
                    model=args.model,
                    input=input_text,
                    timeout=args.timeout,
                )
                story.embedding = vector
                embedded += 1
            except Exception:
                log.exception(
                    "Failed to embed story %s (headline=%s)",
                    story.id,
                    story.headline[:60],
                )
                errors += 1

            # Periodic commit
            if i % args.batch_size == 0:
                session.commit()
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                log.info(
                    "Progress: %d/%d  embedded=%d  errors=%d  (%.1f stories/s)",
                    i,
                    total,
                    embedded,
                    errors,
                    rate,
                )

        # Final commit
        session.commit()

        elapsed = time.time() - t0
        log.info(
            "Embedding backfill complete: %d/%d embedded, %d errors in %.1fs",
            embedded,
            total,
            errors,
            elapsed,
        )


if __name__ == "__main__":
    main()
