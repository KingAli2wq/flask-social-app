"""Utilities for detecting emotions in user text via a GoEmotions model."""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Iterable, Sequence

try:
    import torch
    from torch.nn import functional as F
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    _EMOTION_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional heavy deps
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    AutoModelForSequenceClassification = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    _EMOTION_DEPS_AVAILABLE = False

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_NAME = os.getenv("EMOTION_MODEL_NAME", "bhadresh-savani/distilbert-base-uncased-emotion")
_SCORE_THRESHOLD = float(os.getenv("EMOTION_SCORE_THRESHOLD", "0.15"))
_CACHE_DIR = os.getenv("EMOTION_MODEL_CACHE", None) or None

_tokenizer: AutoTokenizer | None = None
_model: AutoModelForSequenceClassification | None = None
_device: torch.device | None = None
_model_lock = threading.Lock()


class EmotionServiceError(RuntimeError):
    """Raised when the emotion classifier cannot produce a prediction."""


@dataclass(slots=True)
class EmotionPrediction:
    label: str
    score: float


def _resolve_device() -> torch.device:
    if not _EMOTION_DEPS_AVAILABLE or torch is None:
        raise EmotionServiceError("Emotion detection is unavailable (missing torch/transformers)")
    if torch.cuda.is_available():
        return torch.device("cuda")
    try:  # pragma: no cover - optional backend
        if torch.backends.mps.is_available():
            return torch.device("mps")
    except AttributeError:  # pragma: no cover - backend not compiled
        pass
    return torch.device("cpu")


def _load_artifacts() -> tuple[AutoTokenizer, AutoModelForSequenceClassification, torch.device]:
    if not _EMOTION_DEPS_AVAILABLE or torch is None or AutoTokenizer is None or AutoModelForSequenceClassification is None:
        raise EmotionServiceError("Emotion detection is unavailable (missing torch/transformers)")

    global _tokenizer, _model, _device
    if _tokenizer is not None and _model is not None and _device is not None:
        return _tokenizer, _model, _device

    with _model_lock:
        if _tokenizer is None or _model is None or _device is None:
            logger.info("Loading emotion model %s", _DEFAULT_MODEL_NAME)
            tokenizer = AutoTokenizer.from_pretrained(_DEFAULT_MODEL_NAME, cache_dir=_CACHE_DIR)
            model = AutoModelForSequenceClassification.from_pretrained(_DEFAULT_MODEL_NAME, cache_dir=_CACHE_DIR)
            device = _resolve_device()
            model.to(device)
            model.eval()
            _tokenizer = tokenizer
            _model = model
            _device = device
    return _tokenizer, _model, _device


def detect_emotions(
    text: str,
    *,
    top_k: int = 3,
    min_score: float | None = None,
) -> list[EmotionPrediction]:
    """Return the dominant emotions for the provided text ordered by probability."""

    if not _EMOTION_DEPS_AVAILABLE or torch is None or F is None:
        raise EmotionServiceError("Emotion detection is unavailable (missing torch/transformers)")

    cleaned = (text or "").strip()
    if not cleaned:
        return []

    min_threshold = _SCORE_THRESHOLD if min_score is None else max(0.0, min_score)
    tokenizer, model, device = _load_artifacts()

    try:
        inputs = tokenizer(cleaned, return_tensors="pt", truncation=True, padding=True)
        inputs = {key: tensor.to(device) for key, tensor in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
            scores = F.softmax(outputs.logits, dim=-1)[0].detach().cpu()
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Emotion detection failed")
        raise EmotionServiceError("Unable to run emotion classifier") from exc

    labels = getattr(model.config, "id2label", {})
    num_labels = scores.shape[-1]
    resolved_top_k = max(1, min(int(top_k) if top_k else 3, num_labels))

    pairs: list[EmotionPrediction] = []
    for idx in range(num_labels):
        label = labels.get(idx, f"label_{idx}")
        pairs.append(EmotionPrediction(label=label, score=float(scores[idx])))

    pairs.sort(key=lambda item: item.score, reverse=True)
    filtered = [item for item in pairs[:resolved_top_k] if item.score >= min_threshold]
    return filtered


def build_emotion_directive(predictions: Sequence[EmotionPrediction]) -> str | None:
    """Convert predictions into a short directive for the LLM to respond empathetically."""

    if not predictions:
        return None

    parts = [f"{pred.label} ({pred.score:.2f})" for pred in predictions]
    joined = ", ".join(parts)
    return (
        "Emotion insight: the user may be experiencing "
        f"{joined}. Acknowledge these feelings, respond with empathy, and offer uplifting guidance."
    )


def emotions_to_dict(predictions: Iterable[EmotionPrediction]) -> list[dict[str, float]]:
    """Serialize predictions for JSON responses."""

    return [{"label": pred.label, "score": round(pred.score, 6)} for pred in predictions]


__all__ = [
    "EmotionPrediction",
    "EmotionServiceError",
    "detect_emotions",
    "build_emotion_directive",
    "emotions_to_dict",
]