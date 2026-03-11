"""
llm_client.py  —  Phase 1 Intelligence Layer

Central LLM interface for AutoResearch.
Supports multiple providers via LiteLLM (OpenAI, Ollama, Anthropic, etc.)
with automatic retry, JSON parsing, and graceful fallback.

Configuration (src/config/settings.py or .env):
    LLM_PROVIDER   = "ollama"          # or "openai", "anthropic", etc.
    LLM_MODEL      = "llama3"          # provider-specific model name
    LLM_API_BASE   = "http://localhost:11434"   # for Ollama
    LLM_API_KEY    = ""                # empty for local Ollama
    LLM_TIMEOUT    = 60               # seconds per call
    LLM_MAX_RETRIES = 2
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from src.config.settings import LLM_SETTINGS
from src.orchestration.logger import setup_logger

logger = setup_logger()

# ---------------------------------------------------------------------------
# Optional litellm import — graceful degradation if not installed
# ---------------------------------------------------------------------------
try:
    import litellm
    litellm.drop_params = True          # ignore unsupported params silently
    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False
    logger.warning("litellm not installed — LLM features will use fallback stubs")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def call_llm(
    system_prompt: str,
    user_prompt: str,
    expect_json: bool = False,
    temperature: float = 0.2,
) -> str:
    """
    Send a chat completion request to the configured LLM provider.

    Args:
        system_prompt: Role / instruction context for the model.
        user_prompt:   The actual content to process.
        expect_json:   If True, append a JSON-only instruction and validate response.
        temperature:   Sampling temperature (lower = more deterministic).

    Returns:
        Raw text response (str).  If expect_json, returns the first valid JSON
        block found in the response.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    if not _LITELLM_AVAILABLE:
        raise RuntimeError(
            "litellm is not installed. Run: pip install litellm"
        )

    cfg          = LLM_SETTINGS
    model        = cfg.get("model", "ollama/llama3")
    api_base     = cfg.get("api_base")
    api_key      = cfg.get("api_key") or "none"
    timeout      = cfg.get("timeout_seconds", 60)
    max_retries  = cfg.get("max_retries", 2)

    if expect_json:
        system_prompt += (
            "\n\nIMPORTANT: Respond with ONLY valid JSON. "
            "No markdown fences, no preamble, no explanation. "
            "Start your response with '{' or '[' and end with '}' or ']'."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]

    kwargs: dict[str, Any] = {
        "model":       model,
        "messages":    messages,
        "temperature": temperature,
        "timeout":     timeout,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            logger.info(
                f"LLM call attempt {attempt + 1}/{max_retries + 1} "
                f"[model={model}] [expect_json={expect_json}]"
            )
            response   = litellm.completion(**kwargs)
            raw_text   = response.choices[0].message.content or ""

            if expect_json:
                return _extract_json(raw_text)
            return raw_text

        except Exception as exc:
            last_error = exc
            logger.warning(f"LLM attempt {attempt + 1} failed: {exc}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)   # exponential back-off: 1s, 2s

    raise RuntimeError(
        f"LLM call failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def call_llm_json(system_prompt: str, user_prompt: str) -> dict | list:
    """
    Convenience wrapper: always returns parsed Python object (dict or list).
    Raises ValueError if the response cannot be parsed as JSON.
    """
    raw = call_llm(system_prompt, user_prompt, expect_json=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON even after extraction: {exc}\nRaw: {raw[:500]}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """
    Extract the first complete JSON object or array from a string.
    Handles responses wrapped in markdown fences or extra prose.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    text = text.replace("```", "").strip()

    # Try the whole string first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Find first { or [ and attempt to parse from there
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        # Walk from the end to find the last matching bracket
        end = text.rfind(end_char)
        if end == -1 or end <= start:
            continue
        candidate = text[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    # Last resort: return the stripped text and let the caller handle it
    return text