"""Assign email stories to topics via centroid embedding similarity.

Reads stories with embeddings but no topic_id, matches them against existing
topics using pgvector cosine distance, and either assigns to the best match
or creates a new topic.

Usage:
    cd services/worker
    python -m app.llm --topics [--limit N] [--sim-threshold 0.85]
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import select, text, update

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
TOPIC_MATCH_WINDOW_DAYS = 60
TOPIC_EVERGREEN_STORY_COUNT = 20
SIM_THRESHOLD_ASSIGN = 0.85
CANDIDATES_K = 5
# Optional operational guard: only fetch stories from the last N days
STORY_FETCH_WINDOW_DAYS = int(os.environ.get("TOPIC_STORY_FETCH_WINDOW_DAYS", "0"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(vec: list[float]) -> list[float]:
    """Return the L2-normalised version of *vec*."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


# ---------------------------------------------------------------------------
# Core per-story assignment
# ---------------------------------------------------------------------------


def assign_one_story(
    session,
    story,
    *,
    sim_threshold: float,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
) -> dict:
    """Assign a single story to a topic inside the current transaction.

    Returns a dict with decision metadata for logging.
    """
    from app.models import Topic  # local import to keep module-level fast

    t0 = time.time()

    # 1. Normalise the story embedding
    raw_vec = list(story.embedding)
    e = _normalize(raw_vec)
    e_str = "[" + ",".join(str(x) for x in e) + "]"

    # 2. Matchable topics: recent OR evergreen
    cutoff = datetime.now(timezone.utc) - timedelta(days=TOPIC_MATCH_WINDOW_DAYS)

    candidates_sql = text(
        """
        SELECT id,
               centroid_embedding,
               story_count,
               (centroid_embedding <=> :embedding) AS distance
        FROM   topics
        WHERE  last_story_at >= :cutoff
           OR  story_count  >= :evergreen
        ORDER  BY centroid_embedding <=> :embedding
        LIMIT  :k
        """
    )

    rows = session.execute(
        candidates_sql,
        {
            "embedding": e_str,
            "cutoff": cutoff,
            "evergreen": TOPIC_EVERGREEN_STORY_COUNT,
            "k": CANDIDATES_K,
        },
    ).fetchall()

    decision: str
    topic_id: uuid.UUID
    similarity: float | None = None
    story_count_before: int | None = None
    story_count_after: int | None = None
    label: str | None = None

    if rows:
        best = rows[0]
        best_distance = float(best.distance)
        similarity = 1.0 - best_distance  # cosine_similarity = 1 - cosine_distance
    else:
        similarity = None

    if rows and similarity is not None and similarity >= sim_threshold:
        # --- Assign to existing topic ---
        topic_id = best.id
        story_count_before = best.story_count

        # Lock the topic row to prevent concurrent centroid drift
        locked = session.execute(
            text("SELECT centroid_embedding, story_count FROM topics WHERE id = :tid FOR UPDATE"),
            {"tid": topic_id},
        ).fetchone()

        old_count = locked.story_count
        _raw_centroid = locked.centroid_embedding
        if isinstance(_raw_centroid, str):
            import json
            old_centroid = json.loads(_raw_centroid)
        else:
            old_centroid = list(_raw_centroid)

        # Running-mean centroid update  →  new_c = normalize((c*n + e) / (n+1))
        new_raw = [(c * old_count + ei) / (old_count + 1) for c, ei in zip(old_centroid, e)]
        new_centroid = _normalize(new_raw)
        new_c_str = "[" + ",".join(str(x) for x in new_centroid) + "]"

        session.execute(
            text(
                """
                UPDATE topics
                SET    centroid_embedding = :centroid,
                       story_count       = story_count + 1,
                       last_story_at     = now()
                WHERE  id = :tid
                """
            ),
            {"centroid": new_c_str, "tid": topic_id},
        )
        story_count_after = old_count + 1
        decision = "assigned"

        # Link story → topic BEFORE label generation so headline count is correct
        link_result = session.execute(
            update(story.__class__)
            .where(story.__class__.id == story.id)
            .where(story.__class__.topic_id.is_(None))
            .values(topic_id=topic_id)
        )

        if link_result.rowcount == 0:
            # Another worker already assigned this story; roll back topic stats
            session.rollback()
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            return {
                "story_id": str(story.id),
                "decision": "skipped",
                "topic_id": str(topic_id),
                "similarity": round(similarity, 4) if similarity is not None else None,
                "story_count_before": story_count_before,
                "story_count_after": story_count_after,
                "label": None,
                "elapsed_ms": elapsed_ms,
            }

        # Generate/update topic label now that topic has ≥2 stories
        try:
            from app.llm.generate_topic_label import generate_topic_label

            label = generate_topic_label(
                session,
                topic_id,
                ollama_base_url=ollama_base_url,
                ollama_model=ollama_model,
            )
        except Exception:
            label = None
            log.warning(
                "Label generation failed for topic %s",
                topic_id,
                exc_info=True,
            )
    else:
        # --- Create new topic ---
        result = session.execute(
            text(
                """
                INSERT INTO topics (centroid_embedding, story_count, last_story_at)
                VALUES (:centroid, 1, now())
                RETURNING id
                """
            ),
            {"centroid": e_str},
        )
        topic_id = result.scalar_one()
        story_count_before = 0
        story_count_after = 1
        decision = "created"

        # Link story → topic
        link_result = session.execute(
            update(story.__class__)
            .where(story.__class__.id == story.id)
            .where(story.__class__.topic_id.is_(None))
            .values(topic_id=topic_id)
        )

        if link_result.rowcount == 0:
            session.rollback()
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            return {
                "story_id": str(story.id),
                "decision": "skipped",
                "topic_id": str(topic_id),
                "similarity": None,
                "story_count_before": story_count_before,
                "story_count_after": story_count_after,
                "label": None,
                "elapsed_ms": elapsed_ms,
            }

    elapsed_ms = round((time.time() - t0) * 1000, 1)

    return {
        "story_id": str(story.id),
        "decision": decision,
        "topic_id": str(topic_id),
        "similarity": round(similarity, 4) if similarity is not None else None,
        "story_count_before": story_count_before,
        "story_count_after": story_count_after,
        "label": label,
        "elapsed_ms": elapsed_ms,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Assign email stories to topics via centroid matching",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("TOPIC_ASSIGN_LIMIT", "0")),
        help="Max stories to process (0 = all). Default: TOPIC_ASSIGN_LIMIT or 0",
    )
    p.add_argument(
        "--sim-threshold",
        type=float,
        default=SIM_THRESHOLD_ASSIGN,
        help=f"Cosine similarity threshold for assignment (default: {SIM_THRESHOLD_ASSIGN})",
    )
    p.add_argument(
        "--ollama-base-url",
        type=str,
        default=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434"),
        help="Ollama API base URL (default: OLLAMA_BASE_URL or http://ollama:11434)",
    )
    p.add_argument(
        "--ollama-model",
        type=str,
        default=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
        help="Ollama model for label generation (default: OLLAMA_MODEL or llama3.1:8b)",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Run topic assignment for unassigned stories."""
    args = _parse_args(argv)

    # Late imports
    from app.db import get_session
    from app.models import EmailStory

    Session = get_session()

    log.info(
        "Topic assignment starting  sim_threshold=%.2f  limit=%s",
        args.sim_threshold,
        args.limit or "unlimited",
    )

    # Build fetch query
    query = (
        select(EmailStory)
        .where(EmailStory.status == "ok")
        .where(EmailStory.embedding.isnot(None))
        .where(EmailStory.topic_id.is_(None))
        .order_by(EmailStory.processed_at.asc())
    )
    if STORY_FETCH_WINDOW_DAYS:
        cutoff = datetime.now(timezone.utc) - timedelta(days=STORY_FETCH_WINDOW_DAYS)
        query = query.where(EmailStory.processed_at >= cutoff)
    if args.limit:
        query = query.limit(args.limit)

    with Session() as session:
        stories = session.execute(query).scalars().all()

        if not stories:
            log.info("No unassigned stories found. Nothing to do.")
            return

        log.info("Found %d stories to assign", len(stories))

        assigned = 0
        created = 0
        skipped = 0
        t0 = time.time()

        for i, story in enumerate(stories, 1):
            info = assign_one_story(
                session,
                story,
                sim_threshold=args.sim_threshold,
                ollama_base_url=args.ollama_base_url,
                ollama_model=args.ollama_model,
            )
            session.commit()

            if info["decision"] == "assigned":
                assigned += 1
            elif info["decision"] == "created":
                created += 1
            else:
                skipped += 1

            label_str = f"  label={info['label']!r}" if info.get("label") else ""
            log.info(
                "story=%s  decision=%s  topic=%s  sim=%s  "
                "count=%s→%s  elapsed=%sms%s",
                info["story_id"],
                info["decision"],
                info["topic_id"],
                info["similarity"],
                info["story_count_before"],
                info["story_count_after"],
                info["elapsed_ms"],
                label_str,
            )

            if i % 50 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                log.info(
                    "Progress: %d/%d  assigned=%d  created=%d  skipped=%d  (%.1f/s)",
                    i, len(stories), assigned, created, skipped, rate,
                )

        elapsed = time.time() - t0
        log.info(
            "Topic assignment complete: %d assigned, %d created, %d skipped in %.1fs",
            assigned, created, skipped, elapsed,
        )


if __name__ == "__main__":
    main()
