"""Embed desired_actions rows that lack an embedding.

Reads desired_actions where embedding IS NULL, computes an embedding via
Ollama's /api/embed endpoint using the description text, and stores the result.

Usage:
    cd services/worker
    python -m app.llm.embed_desired_actions [--limit N]
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from dotenv import load_dotenv
from sqlalchemy import select

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
        description="Embed desired_actions descriptions",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max actions to embed (0 = all). Default: 0",
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
    """Embed desired_actions without embeddings."""
    args = _parse_args(argv)

    from app.db import get_session
    from app.models import DesiredAction
    from app.llm import ollama_client

    Session = get_session()

    log.info(
        "Desired-actions embedding starting  model=%s  url=%s  limit=%s",
        args.model,
        args.ollama_url,
        args.limit or "unlimited",
    )

    query = (
        select(DesiredAction)
        .where(DesiredAction.embedding.is_(None))
        .where(DesiredAction.active.is_(True))
        .order_by(DesiredAction.created_at.asc())
    )
    if args.limit:
        query = query.limit(args.limit)

    with Session() as session:
        actions = session.execute(query).scalars().all()
        total = len(actions)

        if total == 0:
            log.info("No desired actions without embeddings. Nothing to do.")
            return

        log.info("Found %d desired actions to embed", total)

        embedded = 0
        errors = 0
        t0 = time.time()

        for i, action in enumerate(actions, 1):
            try:
                vector = ollama_client.embed(
                    base_url=args.ollama_url,
                    model=args.model,
                    input=action.description,
                    timeout=args.timeout,
                )
                action.embedding = vector
                embedded += 1
            except Exception:
                log.exception(
                    "Failed to embed desired action %s (desc=%s)",
                    action.id,
                    action.description[:60],
                )
                errors += 1

        session.commit()

        elapsed = time.time() - t0
        log.info(
            "Desired-actions embedding complete: %d/%d embedded, %d errors in %.1fs",
            embedded,
            total,
            errors,
            elapsed,
        )


if __name__ == "__main__":
    main()
