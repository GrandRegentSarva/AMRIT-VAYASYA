"""
Groq Model Orchestration
-------------------------
Handles model selection, rate-limit retries, and fallback chains
for the Groq free tier.

Free tier constraints (as of 2026):
    - 30-60 RPM depending on model
    - 6,000-30,000 TPM depending on model
    - 1,000-14,400 RPD depending on model

Strategy:
    1. Try the primary model (llama-3.3-70b-versatile — best quality)
    2. On rate limit (429), back off and retry once
    3. If still rate-limited, fall back to a smaller model (llama-3.1-8b-instant)
    4. If all models fail, return a structured error

The caller never needs to think about models or retries.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class GroqResponse:
    """Structured response from the Groq orchestration layer."""
    text: str
    model_used: str
    tokens_used: int
    latency_ms: float
    ok: bool
    error: str | None = None


# Model fallback chain — ordered by quality (highest first)
# Each entry: (model_id, max_tokens, description)
_MODEL_CHAIN: list[tuple[str, int, str]] = [
    ('llama-3.3-70b-versatile', 2048, 'Primary: high-quality architectural narration'),
    ('llama-3.1-8b-instant', 2048, 'Fallback: fast, lower quality'),
]

# Rate-limit retry config
_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 2.0


def _get_client():
    """Lazily import and construct the Groq client."""
    try:
        import groq
    except ImportError:
        raise RuntimeError(
            'groq package not installed. Run: pip install groq'
        )

    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        # Try loading from .env via config
        try:
            from config import get_settings
            api_key = get_settings().groq_api_key
        except Exception:
            pass

    if not api_key:
        raise RuntimeError(
            'GROQ_API_KEY not set. Add it to cross-repo/.env or export it.'
        )

    return groq.Groq(api_key=api_key)


def _try_model(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> tuple[str, int] | None:
    """
    Attempt a single completion call with retry on rate-limit.
    Returns (text, tokens_used) on success, None on failure.
    """
    import groq as groq_module

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content or ''
            tokens = getattr(response.usage, 'total_tokens', 0) if response.usage else 0
            return text, tokens

        except groq_module.RateLimitError:
            if attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BACKOFF_SECONDS * (attempt + 1)
                time.sleep(wait)
                continue
            return None

        except groq_module.APIStatusError as exc:
            # Model unavailable or other API error — skip to next model
            return None

    return None


def complete(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.2,
) -> GroqResponse:
    """
    Send a prompt through the Groq model chain with automatic
    rate-limit retry and model fallback.

    Args:
        prompt: The user message content.
        system_prompt: Optional system message for role grounding.
        temperature: Sampling temperature (0.0 - 1.0).

    Returns:
        GroqResponse with the generated text, model used, and metadata.
    """
    try:
        client = _get_client()
    except RuntimeError as exc:
        return GroqResponse(
            text='',
            model_used='none',
            tokens_used=0,
            latency_ms=0,
            ok=False,
            error=str(exc),
        )

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': prompt})

    for model_id, max_tokens, description in _MODEL_CHAIN:
        start = time.monotonic()
        result = _try_model(client, model_id, messages, max_tokens, temperature)
        elapsed_ms = (time.monotonic() - start) * 1000

        if result is not None:
            text, tokens = result
            return GroqResponse(
                text=text,
                model_used=model_id,
                tokens_used=tokens,
                latency_ms=round(elapsed_ms, 1),
                ok=True,
            )

    # All models exhausted
    return GroqResponse(
        text='',
        model_used='none',
        tokens_used=0,
        latency_ms=0,
        ok=False,
        error=(
            'All Groq models rate-limited or unavailable. '
            'Free tier allows ~30 RPM. Wait a minute and try again.'
        ),
    )
