"""Model-agnostic entry point used by the services.

Provider precedence: Anthropic, then Gemini, then ``rules`` (no key configured).
Every caller must handle ``None`` and fall back to deterministic behaviour, so
the product keeps working with no model at all. Decisions that affect safety
(verdicts, consent, credentials) are never delegated to the model.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any

import httpx

from app.ai.prompts import PERSONA
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.base import TIMEOUT_SECONDS, LLMProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.tone import respectful
from app.config import settings

logger = logging.getLogger(__name__)
RULES_PROVIDER = "rules"


@lru_cache(maxsize=1)
def _active_provider() -> LLMProvider | None:
    if settings.anthropic_api_key:
        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    if settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return None


def provider() -> str:
    """Return the active provider name: ``claude``, ``gemini`` or ``rules``."""
    active = _active_provider()
    return active.name if active else RULES_PROVIDER


async def complete(prompt: str, system: str = PERSONA, *, json_output: bool = False) -> str | None:
    """Send one prompt to the configured model.

    Returns:
        The model text in a respectful tone (see ``app.ai.tone``), or ``None`` when
        no provider is configured or the call fails.
    """
    active = _active_provider()
    if active is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            reply = await active.complete(client, prompt, system, json_output=json_output)
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("LLM call failed, falling back to rules: %s", exc)
        return None
    return respectful(reply) if reply else reply


def parse_json(text: str | None) -> dict[str, Any] | None:
    """Extract the first JSON object found in a model reply, if any."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
