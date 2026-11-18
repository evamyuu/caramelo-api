"""Provider contract. Adding a model vendor means adding one class that satisfies it."""

from __future__ import annotations

from typing import Protocol

import httpx

TIMEOUT_SECONDS = 40


class LLMProvider(Protocol):
    """A chat-completion backend."""

    name: str

    async def complete(self, client: httpx.AsyncClient, prompt: str, system: str, *, json_output: bool) -> str:
        """Return the model text for one prompt. May raise ``httpx.HTTPError``/``KeyError``/``IndexError``."""
