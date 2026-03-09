"""Thin HTTP client for the Ollama /api/chat endpoint.

Uses httpx (already in requirements.txt) for synchronous requests.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


def chat(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    timeout: float = 120,
) -> dict[str, Any]:
    """Send a chat completion request to Ollama and return the response dict.

    Returns the full JSON response which includes:
        - message.content  (the assistant reply)
        - prompt_eval_count / eval_count  (token counts, if available)

    Raises httpx.HTTPStatusError on non-2xx responses.
    Raises httpx.TimeoutException on timeout.
    """
    url = f"{base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,
        },
    }

    log.debug("POST %s  model=%s  msgs=%d", url, model, len(messages))

    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    log.debug(
        "Ollama response: prompt_tokens=%s  completion_tokens=%s",
        data.get("prompt_eval_count"),
        data.get("eval_count"),
    )
    return data


def embed(
    *,
    base_url: str,
    model: str,
    input: str,
    timeout: float = 60,
) -> list[float]:
    """Generate an embedding vector for the given text via Ollama /api/embed.

    Returns the embedding as a list of floats.

    Raises httpx.HTTPStatusError on non-2xx responses.
    Raises httpx.TimeoutException on timeout.
    """
    url = f"{base_url.rstrip('/')}/api/embed"
    payload = {
        "model": model,
        "input": input,
    }

    log.debug("POST %s  model=%s  len(input)=%d", url, model, len(input))

    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    embeddings = data.get("embeddings", [])
    if not embeddings:
        raise ValueError(f"Ollama returned no embeddings for model={model}")

    log.debug("Embedding dims=%d", len(embeddings[0]))
    return embeddings[0]
