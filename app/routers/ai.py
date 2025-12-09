"""Router for interacting with the local Social AI model via Ollama."""
from __future__ import annotations

import json
import logging
import os
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.safety import SafetyViolation, check_content_policy

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://143.198.39.198:11434").rstrip("/")
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "huihui_ai/qwen3-abliterated:0.6b-q4_K_M")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))
ALLOW_ADULT_NSFW = os.getenv("ALLOW_ADULT_NSFW", "false").lower() == "true"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    """
    Chat request wrapper.

    confirmed_adult:
        Indicates the user has explicitly confirmed they are 18+ and consent 
        to adult content. This is used together with the server-wide 
        ALLOW_ADULT_NSFW flag. It does NOT bypass any other safety checks.
    """
    message: str
    mode: Literal["default", "freaky", "deep"] = "default"
    history: list[dict[str, str]] | None = None
    confirmed_adult: bool = False



class ChatResponse(BaseModel):
    reply: str


def build_system_prompt(mode: str) -> str:
    prompts = {
        "default": (
            "You are Social AI, a kind and concise assistant embedded inside a social media app. "
            "Offer clear, upbeat responses and gently guide users toward positive interactions."
        ),
        "freaky": (
            "You are Social AI in Freaky mode. Respond with playful, quirky energy and surprising metaphors, "
            "yet remain respectful, safe, and genuinely helpful."
        ),
        "deep": (
            "You are Social AI in Deep mode. Answer thoughtfully with reflective, philosophical insight while staying practical."
        ),
    }
    return prompts.get(mode, prompts["default"])


def _coerce_history(items: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not items:
        return []
    coerced: list[dict[str, str]] = []
    for entry in items:
        role = entry.get("role")
        content = entry.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            coerced.append({"role": role, "content": content})
    return coerced


@router.post("/chat", response_model=ChatResponse)
async def chat_with_local_model(payload: ChatRequest) -> ChatResponse:
    system_prompt = build_system_prompt(payload.mode)
    history_messages = _coerce_history(payload.history)

    full_text_to_moderate = payload.message
    if history_messages:
        recent_context = " ".join(entry["content"] for entry in history_messages[-5:])
        full_text_to_moderate = f"{recent_context} {full_text_to_moderate}".strip()

    allow_adult = ALLOW_ADULT_NSFW and payload.confirmed_adult
    safety = check_content_policy(full_text_to_moderate, allow_adult_nsfw=allow_adult)
    if not safety.allowed:
        logger.warning(
            "AI prompt blocked by app policy | mode=%s allow_adult=%s violations=%s reason=%s",
            payload.mode,
            allow_adult,
            [v.value for v in safety.violations],
            getattr(safety, "reason", None),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Your request violates our content policy.",
                "violations": [v.value for v in safety.violations],
            },
        )

    messages = [{"role": "system", "content": system_prompt}, *history_messages, {"role": "user", "content": payload.message}]

    request_payload = {"model": LOCAL_LLM_MODEL, "messages": messages, "stream": False}

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(OLLAMA_CHAT_URL, json=request_payload)
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        logger.exception("Failed to reach local LLM at %s", OLLAMA_CHAT_URL)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Local LLM is unavailable") from exc

    logger.debug("Ollama status=%s body=%s", response.status_code, response.text[:200])

    if response.status_code >= 400:
        logger.error("Local LLM returned %s: %s", response.status_code, response.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Local LLM returned an error")

    try:
        resp_json = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid response from local LLM") from exc

    message = resp_json.get("message") or {}
    assistant_text = message.get("content")
    if not isinstance(assistant_text, str):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Local LLM response missing assistant text")

    return ChatResponse(reply=assistant_text)


@router.post("/chat/stream")
async def chat_with_local_model_stream(payload: ChatRequest) -> StreamingResponse:
    system_prompt = build_system_prompt(payload.mode)
    history_messages = _coerce_history(payload.history)

    full_text_to_moderate = payload.message
    if history_messages:
        recent_context = " ".join(entry["content"] for entry in history_messages[-5:])
        full_text_to_moderate = f"{recent_context} {full_text_to_moderate}".strip()

    allow_adult = ALLOW_ADULT_NSFW and payload.confirmed_adult
    safety = check_content_policy(full_text_to_moderate, allow_adult_nsfw=allow_adult)
    if not safety.allowed:
        logger.warning(
            "Blocked AI prompt due to safety violations (stream): %s",
            ", ".join(v.value for v in safety.violations),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Your request violates our content policy.",
                "violations": [v.value for v in safety.violations],
            },
        )

    messages = [
        {"role": "system", "content": system_prompt},
        *history_messages,
        {"role": "user", "content": payload.message},
    ]

    request_payload = {"model": LOCAL_LLM_MODEL, "messages": messages, "stream": True}

    client = httpx.AsyncClient(timeout=OLLAMA_TIMEOUT)
    stream_ctx = client.stream("POST", OLLAMA_CHAT_URL, json=request_payload)
    try:
        response = await stream_ctx.__aenter__()
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        await stream_ctx.__aexit__(type(exc), exc, exc.__traceback__)
        await client.aclose()
        logger.exception("Local LLM timed out when starting stream at %s", OLLAMA_CHAT_URL)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Local LLM timed out") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        await stream_ctx.__aexit__(type(exc), exc, exc.__traceback__)
        await client.aclose()
        logger.exception("Failed to start streaming LLM response at %s", OLLAMA_CHAT_URL)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Local LLM is unavailable") from exc

    async def event_generator():
        try:
            async for line in response.aiter_lines():
                if not line or not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("Skipping invalid JSON chunk from local LLM stream: %s", line)
                    continue
                text_fragment = ""
                message_payload = chunk.get("message")
                if isinstance(message_payload, dict):
                    candidate = message_payload.get("content")
                    if isinstance(candidate, str):
                        text_fragment = candidate
                if not text_fragment:
                    delta = chunk.get("delta")
                    if isinstance(delta, str):
                        text_fragment = delta
                if text_fragment:
                    yield text_fragment
        except httpx.HTTPError as exc:  # pragma: no cover - stream failure path
            logger.error("Streaming from local LLM failed: %s", exc)
        finally:
            await stream_ctx.__aexit__(None, None, None)
            await client.aclose()

    return StreamingResponse(event_generator(), media_type="text/plain")


__all__ = [
    "router",
    "chat_with_local_model",
    "chat_with_local_model_stream",
    "ChatRequest",
    "ChatResponse",
    "build_system_prompt",
]
