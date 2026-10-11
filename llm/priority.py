"""Is a recurring expense high priority (insurance, rent, loans) or low priority (streaming, delivery, gym)?

One bounded Gemini call over the expense names only (no amounts, no ids), cached by name. Without a key,
or if the call fails, a keyword list answers instead, so the audit never depends on the network.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parent / "priority_cache.json"
HIGH_WORDS = ("insur", "rent", "mortgage", "loan", "lease", "auto", "car payment", "student", "utilit", "electric",
              "water", "power", "gas", "internet", "wifi", "phone", "wireless", "t-mobile", "verizon", "at&t",
              "comcast", "xfinity", "geico", "progressive", "allstate", "state farm", "tuition", "childcare",
              "daycare", "medical", "pharmacy", "hoa", "tax", "credit card", "transit")


def _norm(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def keyword_priority(label: str) -> str:
    low = _norm(label)
    tokens = set(re.split(r"[^a-z0-9&-]+", low))
    for word in HIGH_WORDS:
        if (word in tokens) if word in ("rent", "gas", "tax", "auto", "power", "water") else (word in low):
            return "high"
    return "low"


def _load() -> dict[str, str]:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _ask_gemini(labels: list[str]) -> dict[str, str]:
    from llm.gemini import generate_text

    prompt = (
        "Classify each recurring expense name as \"high\" priority (hard to cut: housing, insurance, loans, "
        "utilities, phone, transport to work, medical, childcare) or \"low\" priority (optional: streaming, "
        "food delivery, gym, subscriptions, shopping, entertainment). Return only a JSON object mapping each "
        "name exactly as given to \"high\" or \"low\".\n" + json.dumps(labels)
    )
    raw = json.loads(generate_text(prompt, max_output_tokens=400, json_mode=True))
    return {label: raw[label] for label in labels if raw.get(label) in ("high", "low")}


def classify_labels(labels: list[str], use_gemini: bool | None = None) -> dict[str, str]:
    """label -> "high" | "low". Gemini answers are cached; the keyword list covers anything missing."""
    cache = _load()
    unknown = [lb for lb in labels if _norm(lb) not in cache]
    if unknown and (use_gemini if use_gemini is not None else bool(os.getenv("GEMINI_API_KEY"))):
        try:
            for label, value in _ask_gemini(unknown).items():
                cache[_norm(label)] = value
            CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))
        except Exception as exc:  # network, quota, bad JSON: fall back, never fail the audit
            logger.warning("priority_gemini_failed error_type=%s", type(exc).__name__)
    return {lb: cache.get(_norm(lb)) or keyword_priority(lb) for lb in labels}
