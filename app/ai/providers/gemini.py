"""Google Gemini provider (free tier friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass(frozen=True)
class GeminiProvider:
    api_key: str
    model: str
    name: str = "gemini"

    async def complete(self, client: httpx.AsyncClient, prompt: str, system: str, *, json_output: bool) -> str:
        body: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
        }
        if json_output:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        response = await client.post(
            f"{_BASE_URL}/{self.model}:generateContent", headers={"x-goog-api-key": self.api_key}, json=body
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
