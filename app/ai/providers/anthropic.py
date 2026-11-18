"""Anthropic Messages API provider."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_MAX_TOKENS = 700


@dataclass(frozen=True)
class AnthropicProvider:
    api_key: str
    model: str
    name: str = "claude"

    async def complete(self, client: httpx.AsyncClient, prompt: str, system: str, *, json_output: bool) -> str:
        response = await client.post(
            _URL,
            headers={"x-api-key": self.api_key, "anthropic-version": _API_VERSION},
            json={
                "model": self.model,
                "max_tokens": _MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
