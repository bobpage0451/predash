"""Sender upsert stage.

Aggregates stats from emails_raw + email_filter_metrics + email_stories
and upserts into the senders table. The `email` column stores the raw
from_addr value (e.g. "Business Insider <newsletter@email.businessinsider.com>").
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.db import get_engine

log = logging.getLogger(__name__)

_UPSERT_SQL = text("""
WITH
-- Step 1: flatten all tags per sender (from_addr)
sender_tags AS (
    SELECT
        er.from_addr,
        tag_key,
        SUM(tag_val) AS tag_cnt
    FROM emails_raw er
    JOIN email_stories es ON es.email_id = er.id AND es.status = 'ok'
    CROSS JOIN LATERAL (
        -- Array tags: ["AI", "Tech"]
        SELECT tval AS tag_key, 1 AS tag_val
        FROM jsonb_array_elements_text(
            CASE jsonb_typeof(es.tags) WHEN 'array' THEN es.tags ELSE '[]'::jsonb END
        ) AS tval
        UNION ALL
        -- Object tags: {"AI": 2, "Tech": 1}
        SELECT kv.key AS tag_key, kv.value::int AS tag_val
        FROM jsonb_each_text(
            CASE jsonb_typeof(es.tags) WHEN 'object' THEN es.tags ELSE '{}'::jsonb END
        ) AS kv(key, value)
    ) tag_rows
    WHERE er.from_addr IS NOT NULL AND er.from_addr <> ''
    GROUP BY er.from_addr, tag_key
),
-- Step 2: aggregate tags into a jsonb map per sender
sender_tag_map AS (
    SELECT from_addr, jsonb_object_agg(tag_key, tag_cnt) AS tag_counts
    FROM sender_tags
    GROUP BY from_addr
),
-- Step 3: aggregate email counts and timestamps per sender
sender_agg AS (
    SELECT
        er.from_addr,
        COUNT(DISTINCT er.id) AS total_emails,
        COUNT(DISTINCT er.id) FILTER (
            WHERE efm.filter_outcome IS NOT NULL
              AND efm.filter_outcome <> 'pass'
        ) AS skipped_emails,
        MAX(er.ingested_at) AS last_seen_at,
        MIN(er.ingested_at) AS first_seen_at
    FROM emails_raw er
    LEFT JOIN email_filter_metrics efm ON efm.email_id = er.id
    WHERE er.from_addr IS NOT NULL AND er.from_addr <> ''
    GROUP BY er.from_addr
)
INSERT INTO senders (email, total_emails, skipped_emails, tag_counts, first_seen_at, last_seen_at)
SELECT
    sa.from_addr,
    sa.total_emails,
    sa.skipped_emails,
    stm.tag_counts,
    sa.first_seen_at,
    sa.last_seen_at
FROM sender_agg sa
LEFT JOIN sender_tag_map stm ON stm.from_addr = sa.from_addr
ON CONFLICT (email) DO UPDATE
    SET total_emails   = EXCLUDED.total_emails,
        skipped_emails = EXCLUDED.skipped_emails,
        tag_counts     = EXCLUDED.tag_counts,
        last_seen_at   = GREATEST(senders.last_seen_at, EXCLUDED.last_seen_at),
        first_seen_at  = LEAST(senders.first_seen_at, EXCLUDED.first_seen_at)
""")


def main(argv: list[str] | None = None) -> None:  # noqa: ARG001
    """Upsert all sender stats derived from existing email data."""
    engine = get_engine()

    with engine.begin() as conn:
        result = conn.execute(_UPSERT_SQL)
        log.info("upsert_senders: upserted/updated %d sender rows", result.rowcount)
