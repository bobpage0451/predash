"""Match email stories against active desired actions.

Uses pgvector cosine distance to find (story, desired_action) pairs
above a similarity threshold. Optionally boosts matches where the
story's action_type also matches the desired action's action_types list.

Usage:
    cd services/worker
    python -m app.llm.match_actions [--limit N] [--sim-threshold 0.72]
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SIM_THRESHOLD = 0.72


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Match email stories against desired actions",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("ACTION_MATCH_LIMIT", "0")),
        help="Max stories to consider (0 = all). Default: ACTION_MATCH_LIMIT or 0",
    )
    p.add_argument(
        "--sim-threshold",
        type=float,
        default=float(os.environ.get("ACTION_SIM_THRESHOLD", str(SIM_THRESHOLD))),
        help=f"Cosine similarity threshold (default: {SIM_THRESHOLD})",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Run action matching for new stories against active desired actions."""
    args = _parse_args(argv)

    from app.db import get_session

    Session = get_session()

    log.info(
        "Action matching starting  sim_threshold=%.2f  limit=%s",
        args.sim_threshold,
        args.limit or "unlimited",
    )

    # Build the matching query:
    # Cross-join active desired actions (with embeddings) against stories
    # that have embeddings and haven't been matched yet for that action.
    # Use pgvector <=> (cosine distance) and filter by threshold.
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""

    match_sql = text(f"""
        INSERT INTO action_matches (desired_action_id, story_id, similarity_score, action_type_matched)
        SELECT
            da.id                                    AS desired_action_id,
            es.id                                    AS story_id,
            (1.0 - (es.embedding <=> da.embedding))  AS similarity_score,
            CASE
                WHEN da.action_types IS NOT NULL
                     AND es.action_type IS NOT NULL
                     AND da.action_types @> to_jsonb(es.action_type)
                THEN true
                ELSE false
            END                                      AS action_type_matched
        FROM desired_actions da
        CROSS JOIN LATERAL (
            SELECT es2.*
            FROM email_stories es2
            WHERE es2.status = 'ok'
              AND es2.embedding IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM action_matches am
                  WHERE am.desired_action_id = da.id
                    AND am.story_id = es2.id
              )
            ORDER BY es2.embedding <=> da.embedding
            {limit_clause}
        ) es
        WHERE da.active = true
          AND da.embedding IS NOT NULL
          AND (1.0 - (es.embedding <=> da.embedding)) >= :threshold
        ON CONFLICT (desired_action_id, story_id) DO NOTHING
        RETURNING desired_action_id, story_id, similarity_score, action_type_matched
    """)

    t0 = time.time()

    with Session() as session:
        result = session.execute(match_sql, {"threshold": args.sim_threshold})
        rows = result.fetchall()
        session.commit()

    elapsed = time.time() - t0

    if not rows:
        log.info("No new action matches found. Nothing to do.")
        return

    # Log results
    for row in rows:
        log.info(
            "  MATCH  action=%s  story=%s  sim=%.4f  type_matched=%s",
            row.desired_action_id,
            row.story_id,
            row.similarity_score,
            row.action_type_matched,
        )

    log.info(
        "Action matching complete: %d new matches in %.1fs",
        len(rows),
        elapsed,
    )


if __name__ == "__main__":
    main()
