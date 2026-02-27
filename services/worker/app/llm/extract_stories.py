"""One-shot LLM story extraction from emails_raw → email_stories.

Reads unprocessed emails, sends each to a local Ollama instance to extract
individual stories/topics, and stores them as separate rows in email_stories.

Usage
-----
    cd services/worker
    python -m app.llm --stories                # defaults from .env
    python -m app.llm --stories --limit 10     # process at most 10
    python -m app.llm --stories --model llama3:8b
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import func, select, and_
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.llm import ollama_client
from app.models import EmailRaw, EmailStory

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers (previously in process_emails.py)
# ---------------------------------------------------------------------------


def _email_timestamp(cls=EmailRaw):
    """COALESCE(date_received, ingested_at) — one expression reused everywhere."""
    return func.coalesce(cls.date_received, cls.ingested_at)


def _build_user_prompt(email_row: EmailRaw) -> str:
    """Build the per-email USER message for the LLM."""
    from_addr = email_row.from_addr or "(unknown)"
    subject = email_row.subject or "(no subject)"
    date = str(email_row.date_sent or email_row.date_received or "unknown")

    # Prefer plain text; fall back to stripped HTML
    body = email_row.body_text
    if not body and email_row.body_html:
        try:
            from bs4 import BeautifulSoup
            body = BeautifulSoup(email_row.body_html, "html.parser").get_text(separator="\n")
        except Exception:
            body = email_row.body_html
    if not body:
        body = "(empty body)"

    # Truncate very long bodies to avoid excessive token usage
    max_body_chars = 8000
    if len(body) > max_body_chars:
        body = body[:max_body_chars] + "\n… (truncated)"

    return f"From: {from_addr}\nSubject: {subject}\nDate: {date}\n\nBody:\n{body}"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

STORIES_SYSTEM_PROMPT = """\
You are an email analyst that extracts distinct stories from emails.

Return STRICT JSON only (no markdown, no prose outside JSON).
Always write in English.

Given an email (often a newsletter), identify each distinct story, topic,
or piece of news discussed. For each one, produce:
- headline: a short one-line title (max ~10 words)
- summary: 1–2 sentences describing this specific story
- tags: a flat list of broad categorical tags for THIS story only
  (e.g. "fintech", "regulation", "AI", "gold", "Europe").
  Prefer general/reusable labels over email-specific actions.
- action_type: classify the kind of action this story enables for the reader.
  Use ONE of the following values, or null if the story is purely informational
  with no actionable element:
  "discount_offer"       – a sale, price drop, or discount promotion
  "coupon"               – a redeemable coupon or promo code
  "job_posting"          – a job opening or career opportunity
  "event"                – an event, webinar, conference, or meetup
  "deadline"             – an upcoming deadline or expiration
  "subscription_offer"   – a new subscription, trial, or membership offer
  "informational"        – useful info that might help someone researching a topic
  null                   – none of the above / pure news

Rules:
- If the email covers 5 different topics, return 5 separate objects.
- If the email is about just one thing, return 1 object.
- Do NOT merge unrelated topics into a single story.
- Do NOT invent details. Be concise.
- Each story should be self-contained and understandable on its own.

Output a JSON object with key "stories" containing an array of objects,
each with keys: headline, summary, tags, action_type.

Example output:
{"stories": [
  {"headline": "ECB holds rates steady", "summary": "The European Central Bank kept interest rates unchanged at 4.5%, citing persistent inflation.", "tags": ["ECB", "interest rates", "Europe", "monetary policy"], "action_type": null},
  {"headline": "Stripe launches AI fraud detection", "summary": "Stripe announced a new AI-powered fraud detection tool for online merchants.", "tags": ["Stripe", "AI", "fraud", "fintech"], "action_type": "informational"},
  {"headline": "Tommy Hilfiger 40% off winter sale", "summary": "Tommy Hilfiger is offering 40% off their winter collection through February 28.", "tags": ["Tommy Hilfiger", "fashion", "sale"], "action_type": "discount_offer"}
]}"""

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract individual stories from emails via Ollama LLM.",
    )
    p.add_argument("--limit", type=int, default=None, help="Max emails to process (default: EMAIL_PROCESS_LIMIT env or 50)")
    p.add_argument("--source", type=str, default=None, help="Filter by EmailRaw.source")
    p.add_argument("--mailbox", type=str, default=None, help="Filter by EmailRaw.mailbox")
    p.add_argument("--model", type=str, default=None, help="Ollama model (overrides OLLAMA_MODEL env)")
    p.add_argument("--prompt-version", type=str, default=None, help="Prompt version tag (overrides STORIES_PROMPT_VERSION env)")
    p.add_argument("--processor", type=str, default=None, help="Processor name (overrides PROCESSOR_NAME env)")
    p.add_argument(
        "--no-since-last",
        dest="since_last",
        action="store_false",
        default=True,
        help="Disable checkpoint-based filtering (process all unprocessed emails)",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_checkpoint(session, processor: str, model: str, prompt_version: str) -> datetime | None:
    """Return the email timestamp of the most recently story-extracted row for this run tuple."""
    latest = (
        select(EmailStory.email_id)
        .where(
            EmailStory.processor == processor,
            EmailStory.model == model,
            EmailStory.prompt_version == prompt_version,
        )
        .order_by(EmailStory.processed_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    row = session.execute(
        select(_email_timestamp()).where(EmailRaw.id == latest)
    ).scalar()

    return row


def _build_candidate_query(
    *,
    processor: str,
    model: str,
    prompt_version: str,
    checkpoint: datetime | None,
    since_last: bool,
    source: str | None,
    mailbox: str | None,
    limit: int,
):
    """Build the SELECT for candidate EmailRaw rows to extract stories from."""

    # NOT EXISTS: exclude already-processed rows for this run tuple
    already_extracted = (
        select(EmailStory.id)
        .where(
            EmailStory.email_id == EmailRaw.id,
            EmailStory.processor == processor,
            EmailStory.model == model,
            EmailStory.prompt_version == prompt_version,
        )
        .correlate(EmailRaw)
        .exists()
    )

    conditions = [~already_extracted]

    if since_last and checkpoint is not None:
        conditions.append(_email_timestamp() > checkpoint)

    if source is not None:
        conditions.append(EmailRaw.source == source)
    if mailbox is not None:
        conditions.append(EmailRaw.mailbox == mailbox)

    stmt = (
        select(EmailRaw)
        .where(and_(*conditions))
        .order_by(_email_timestamp().asc())
        .limit(limit)
    )
    return stmt


def _process_one(
    *,
    email_row: EmailRaw,
    processor: str,
    model: str,
    prompt_version: str,
    ollama_base_url: str,
    ollama_timeout: float,
) -> list[EmailStory]:
    """Call Ollama for a single email and return a list of EmailStory rows.

    On LLM or parse failure, returns a single-element list with status='error'.
    """
    user_prompt = _build_user_prompt(email_row)
    messages = [
        {"role": "system", "content": STORIES_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    t0 = time.monotonic()
    try:
        resp = ollama_client.chat(
            base_url=ollama_base_url,
            model=model,
            messages=messages,
            temperature=0.2,
            timeout=ollama_timeout,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        content = resp.get("message", {}).get("content", "")
        tokens_in = resp.get("prompt_eval_count")
        tokens_out = resp.get("eval_count")

        parsed = json.loads(content)
        stories_data = parsed.get("stories", [])

        if not stories_data:
            return [EmailStory(
                email_id=email_row.id,
                story_index=0,
                headline="(no stories extracted)",
                summary="The LLM returned an empty stories array.",
                tags=None,
                processor=processor,
                model=model,
                prompt_version=prompt_version,
                status="ok",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=elapsed_ms,
            )]

        results = []
        for idx, story in enumerate(stories_data):
            raw_action = story.get("action_type")
            action_type = raw_action if isinstance(raw_action, str) else None
            results.append(EmailStory(
                email_id=email_row.id,
                story_index=idx,
                headline=story.get("headline", "(no headline)")[:500],
                summary=story.get("summary", "(no summary)")[:2000],
                tags=story.get("tags", []),
                action_type=action_type,
                processor=processor,
                model=model,
                prompt_version=prompt_version,
                status="ok",
                tokens_in=tokens_in if idx == 0 else None,  # attribute tokens to first story
                tokens_out=tokens_out if idx == 0 else None,
                latency_ms=elapsed_ms if idx == 0 else None,
            ))
        return results

    except json.JSONDecodeError as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_output = resp.get("message", {}).get("content", "") if "resp" in dir() else ""
        log.warning("JSON parse error for email %s: %s", email_row.id, exc)
        return [EmailStory(
            email_id=email_row.id,
            story_index=0,
            headline="Processing failed",
            summary="Story extraction failed: invalid JSON from LLM.",
            tags=None,
            processor=processor,
            model=model,
            prompt_version=prompt_version,
            status="error",
            error_message=f"JSONDecodeError: {exc}",
            tokens_in=resp.get("prompt_eval_count") if "resp" in dir() else None,
            tokens_out=resp.get("eval_count") if "resp" in dir() else None,
            latency_ms=elapsed_ms,
        )]

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.warning("Processing error for email %s: %s", email_row.id, exc)
        return [EmailStory(
            email_id=email_row.id,
            story_index=0,
            headline="Processing failed",
            summary=f"Story extraction failed: {type(exc).__name__}",
            tags=None,
            processor=processor,
            model=model,
            prompt_version=prompt_version,
            status="error",
            error_message=str(exc)[:2000],
            latency_ms=elapsed_ms,
        )]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Run the one-shot LLM story extraction."""
    load_dotenv()
    args = _parse_args(argv)

    # ── Config ──────────────────────────────────────────────────────────
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
    model = args.model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    processor = args.processor or os.environ.get("PROCESSOR_NAME", "ollama")
    prompt_version = args.prompt_version or os.environ.get("STORIES_PROMPT_VERSION", "stories-v2")
    ollama_timeout = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))
    default_limit = int(os.environ.get("EMAIL_PROCESS_LIMIT", "50"))
    limit = args.limit if args.limit is not None else default_limit

    log.info(
        "Stories config: model=%s  processor=%s  prompt_version=%s  limit=%d  since_last=%s",
        model, processor, prompt_version, limit, args.since_last,
    )

    # ── Checkpoint ──────────────────────────────────────────────────────
    Session = get_session()

    with Session() as session:
        checkpoint = _get_checkpoint(session, processor, model, prompt_version)

    if checkpoint is not None:
        log.info("Checkpoint: last story-extracted email timestamp = %s", checkpoint)
    else:
        log.info("No checkpoint found (first run). Processing from oldest.")

    # ── Candidate selection ─────────────────────────────────────────────
    with Session() as session:
        stmt = _build_candidate_query(
            processor=processor,
            model=model,
            prompt_version=prompt_version,
            checkpoint=checkpoint,
            since_last=args.since_last,
            source=args.source,
            mailbox=args.mailbox,
            limit=limit,
        )
        candidates = session.execute(stmt).scalars().all()

    if not candidates:
        log.info("No unprocessed emails found for story extraction. Nothing to do.")
        return

    log.info("Found %d candidate email(s) for story extraction.", len(candidates))

    # ── Process ─────────────────────────────────────────────────────────
    ok_count = 0
    err_count = 0
    skip_count = 0
    story_count = 0

    for i, email_row in enumerate(candidates, 1):
        subject_preview = (email_row.subject or "(no subject)")[:60]
        log.info("[%d/%d] Extracting stories: %s", i, len(candidates), subject_preview)

        story_rows = _process_one(
            email_row=email_row,
            processor=processor,
            model=model,
            prompt_version=prompt_version,
            ollama_base_url=ollama_base_url,
            ollama_timeout=ollama_timeout,
        )

        with Session() as session:
            try:
                session.add_all(story_rows)
                session.commit()

                has_error = any(r.status == "error" for r in story_rows)
                if has_error:
                    err_count += 1
                    log.warning("  ✗ ERROR: %s", story_rows[0].error_message)
                else:
                    ok_count += 1
                    story_count += len(story_rows)
                    log.info(
                        "  ✓ OK  stories=%d  latency=%dms  tokens_in=%s  tokens_out=%s",
                        len(story_rows),
                        story_rows[0].latency_ms or 0,
                        story_rows[0].tokens_in,
                        story_rows[0].tokens_out,
                    )
            except IntegrityError:
                session.rollback()
                skip_count += 1
                log.debug("  – Duplicate (IntegrityError), skipped")

    # ── Summary ─────────────────────────────────────────────────────────
    log.info(
        "Done. emails=%d  ok=%d  errors=%d  skipped=%d  total_stories=%d",
        len(candidates), ok_count, err_count, skip_count, story_count,
    )


if __name__ == "__main__":
    main()
