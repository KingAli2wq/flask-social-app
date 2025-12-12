from __future__ import annotations

import logging
from typing import Iterable, List

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


class EmbeddingClientError(RuntimeError):
    """Raised when embedding generation fails."""


async def embed_text(text: str) -> list[float]:
    """Generate an embedding for the supplied text using the configured Ollama endpoint.

    Returns a list of floats. If the upstream call fails, raises EmbeddingClientError.
    """

    payload = {"model": _settings.ollama_embed_model, "prompt": text}
    timeout = float(getattr(_settings, "ollama_timeout", 60.0) or 60.0)
    url = f"{_settings.ollama_base_url.rstrip('/')}/api/embeddings"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # pragma: no cover - network bound
        logger.exception("Embedding request failed")
        raise EmbeddingClientError("Embedding request failed") from exc

    vector = data.get("embedding") if isinstance(data, dict) else None
    if not isinstance(vector, Iterable):
        raise EmbeddingClientError("Invalid embedding response")
    result: List[float] = []
    for value in vector:
        try:
            result.append(float(value))
        except (TypeError, ValueError) as exc:
            raise EmbeddingClientError("Non-numeric embedding component") from exc
    if not result:
        raise EmbeddingClientError("Empty embedding returned")
    return result


__all__ = ["embed_text", "EmbeddingClientError"]
