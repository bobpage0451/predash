"""Generate or update a topic label using Ollama LLM.

When a topic accumulates ≥2 stories, we feed all story headlines to the LLM
and ask for a short (2-6 word) label that captures the common theme.

Single-story topics are left unlabelled — the topic *is* that story.
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy import select, text

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a news topic labeller.
Given a list of story headlines that belong to the same topic, output a short \
label (2-6 words) that captures the common theme.
Output ONLY the label, nothing else. No quotes, no punctuation, no explanation."""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_topic_label(
    session,
    topic_id: uuid.UUID,
    *,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
) -> str | None:
    """Generate a topic label from its stories' headlines via Ollama.

    Returns the generated label, or None if:
      - The topic has fewer than 2 stories (no label needed)
      - The LLM call fails (logged as a warning; non-fatal)
    """
    from app.llm import ollama_client
    from app.models import EmailStory

    base_url = ollama_base_url or os.environ.get(
        "OLLAMA_BASE_URL", "http://ollama:11434"
    )
    model = ollama_model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

    # Fetch all headlines for this topic
    headlines = (
        session.execute(
            select(EmailStory.headline)
            .where(EmailStory.topic_id == topic_id)
            .order_by(EmailStory.processed_at.asc())
        )
        .scalars()
        .all()
    )

    if len(headlines) < 2:
        return None

    # Build user prompt
    numbered = "\n".join(f"{i}. {h}" for i, h in enumerate(headlines, 1))
    user_prompt = f"Here are {len(headlines)} story headlines from the same topic:\n\n{numbered}"

    try:
        resp = ollama_client.chat(
            base_url=base_url,
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            timeout=30,
        )

        label = resp.get("message", {}).get("content", "").strip()
        if not label:
            log.warning("Ollama returned empty label for topic %s", topic_id)
            return None

        # Persist the label
        session.execute(
            text("UPDATE topics SET label = :label WHERE id = :tid"),
            {"label": label, "tid": topic_id},
        )

        return label

    except Exception:
        log.warning(
            "Label generation failed for topic %s", topic_id, exc_info=True
        )
        return None
