"""Full pipeline runner.

Runs all four worker stages sequentially:
  1. IMAP ingest        (emails_raw)
  2. Story extraction   (email_stories)
  3. Embedding backfill (email_stories.embedding)
  4. Topic assignment   (topics + email_stories.topic_id)

Usage
-----
    cd services/worker
    python -m app                          # run full pipeline
    python -m app --limit 10              # forward --limit to sub-stages
    python -m app --stop-on-error         # abort on first failure
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

STAGES = [
    {
        "name": "IMAP Ingest",
        "description": "Fetch new emails via IMAP → emails_raw",
    },
    {
        "name": "Story Extraction",
        "description": "LLM extraction from emails_raw → email_stories",
    },
    {
        "name": "Embedding Backfill",
        "description": "Compute embeddings for email_stories",
    },
    {
        "name": "Topic Assignment",
        "description": "Assign stories to topics via centroid matching",
    },
    {
        "name": "Embed Desired Actions",
        "description": "Compute embeddings for new desired actions",
    },
    {
        "name": "Action Matching",
        "description": "Match stories against desired actions",
    },
]

BANNER_WIDTH = 60


def _banner(stage_num: int, total: int, name: str, description: str) -> str:
    header = f"Stage {stage_num}/{total}: {name}"
    return (
        "\n"
        f"{'═' * BANNER_WIDTH}\n"
        f"  {header}\n"
        f"  {description}\n"
        f"{'═' * BANNER_WIDTH}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the full Presence worker pipeline end-to-end.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max items to process per stage (forwarded to sub-commands)",
    )
    p.add_argument(
        "--source",
        type=str,
        default=None,
        help="Filter by source (forwarded to story extraction)",
    )
    p.add_argument(
        "--mailbox",
        type=str,
        default=None,
        help="Filter by mailbox (forwarded to story extraction)",
    )
    p.add_argument(
        "--stop-on-error",
        action="store_true",
        default=False,
        help="Abort the pipeline on the first stage failure (default: continue)",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


def _run_imap_ingest() -> None:
    """Run IMAP ingestion (config via environment variables)."""
    from app.imap.ingest import main as imap_main

    imap_main()


def _run_extract_stories(argv: list[str]) -> None:
    """Run LLM story extraction."""
    from app.llm.extract_stories import main as stories_main

    stories_main(argv)


def _run_compute_embeddings(argv: list[str]) -> None:
    """Run embedding backfill."""
    from app.llm.compute_embeddings import main as embed_main

    embed_main(argv)


def _run_assign_topics(argv: list[str]) -> None:
    """Run topic assignment."""
    from app.llm.assign_topics import main as topics_main

    topics_main(argv)


def _run_embed_desired_actions(argv: list[str]) -> None:
    """Run desired actions embedding."""
    from app.llm.embed_desired_actions import main as embed_actions_main

    embed_actions_main(argv)


def _run_match_actions(argv: list[str]) -> None:
    """Run action matching."""
    from app.llm.match_actions import main as match_main

    match_main(argv)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(argv: list[str] | None = None) -> None:
    """Execute the full pipeline end-to-end."""
    args = _parse_args(argv)
    total = len(STAGES)

    log.info("Pipeline starting with %d stages", total)
    if args.limit:
        log.info("  --limit %d will be forwarded to sub-stages", args.limit)

    # Build argv lists for sub-stages that accept them
    stories_argv: list[str] = []
    embed_argv: list[str] = []
    topics_argv: list[str] = []
    embed_actions_argv: list[str] = []
    match_actions_argv: list[str] = []

    if args.limit:
        stories_argv.extend(["--limit", str(args.limit)])
        embed_argv.extend(["--limit", str(args.limit)])
        topics_argv.extend(["--limit", str(args.limit)])
        match_actions_argv.extend(["--limit", str(args.limit)])
    if args.source:
        stories_argv.extend(["--source", args.source])
    if args.mailbox:
        stories_argv.extend(["--mailbox", args.mailbox])

    # Also set IMAP_LIMIT env if --limit was given (IMAP reads from env)
    if args.limit and not os.environ.get("IMAP_LIMIT"):
        os.environ["IMAP_LIMIT"] = str(args.limit)

    runners = [
        lambda: _run_imap_ingest(),
        lambda: _run_extract_stories(stories_argv),
        lambda: _run_compute_embeddings(embed_argv),
        lambda: _run_assign_topics(topics_argv),
        lambda: _run_embed_desired_actions(embed_actions_argv),
        lambda: _run_match_actions(match_actions_argv),
    ]

    pipeline_t0 = time.time()
    results: list[dict] = []

    for i, (stage, runner) in enumerate(zip(STAGES, runners), 1):
        log.info(_banner(i, total, stage["name"], stage["description"]))

        stage_t0 = time.time()
        try:
            runner()
            elapsed = time.time() - stage_t0
            log.info(
                "✓ %s completed in %.1fs",
                stage["name"],
                elapsed,
            )
            results.append({"stage": stage["name"], "status": "ok", "elapsed": elapsed})

        except SystemExit as exc:
            elapsed = time.time() - stage_t0
            # Some stages call sys.exit on missing config — treat exit(0) as ok
            if exc.code in (None, 0):
                log.info(
                    "✓ %s completed (exited cleanly) in %.1fs",
                    stage["name"],
                    elapsed,
                )
                results.append({"stage": stage["name"], "status": "ok", "elapsed": elapsed})
            else:
                log.error(
                    "✗ %s failed (exit code %s) after %.1fs",
                    stage["name"],
                    exc.code,
                    elapsed,
                )
                results.append({"stage": stage["name"], "status": "error", "elapsed": elapsed})
                if args.stop_on_error:
                    log.error("--stop-on-error is set, aborting pipeline.")
                    break

        except Exception:
            elapsed = time.time() - stage_t0
            log.exception(
                "✗ %s failed after %.1fs",
                stage["name"],
                elapsed,
            )
            results.append({"stage": stage["name"], "status": "error", "elapsed": elapsed})
            if args.stop_on_error:
                log.error("--stop-on-error is set, aborting pipeline.")
                break

    # ── Summary ─────────────────────────────────────────────────────────────
    total_elapsed = time.time() - pipeline_t0
    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = sum(1 for r in results if r["status"] == "error")

    log.info("")
    log.info("═" * BANNER_WIDTH)
    log.info("  Pipeline Summary")
    log.info("═" * BANNER_WIDTH)
    for r in results:
        icon = "✓" if r["status"] == "ok" else "✗"
        log.info("  %s %-25s  %6.1fs", icon, r["stage"], r["elapsed"])
    log.info("─" * BANNER_WIDTH)
    log.info(
        "  Total: %d ok, %d errors, %.1fs elapsed",
        ok_count,
        err_count,
        total_elapsed,
    )
    log.info("═" * BANNER_WIDTH)


if __name__ == "__main__":
    run_pipeline()
