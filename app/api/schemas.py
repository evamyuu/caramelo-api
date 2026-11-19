"""Request models for the HTTP API."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

# State (UF) of the user, set when Caramelo is configured. Only the state is kept, never the city.
Region = Field(default=None, pattern=r"^[A-Za-z]{2}$", examples=["SP"])


class LinkScanRequest(BaseModel):
    """Body of ``POST /api/v1/links/scan``."""

    url: str = Field(min_length=3, max_length=2048, examples=["https://example.com"])
    region: str | None = Region


class CallAssessmentRequest(BaseModel):
    """Body of ``POST /api/v1/calls/assess``. Keys are defined in ``risk.CALL_SIGNALS``."""

    signals: dict[str, bool]
    region: str | None = Region


class ChatRequest(BaseModel):
    """Body of ``POST /api/v1/assistant/chat``."""

    message: str = Field(min_length=1, max_length=1000)


class RoutineRequest(BaseModel):
    """Body of ``POST /api/v1/routines``: what the user said, or a learned suggestion to accept."""

    text: str | None = Field(default=None, min_length=3, max_length=300)
    suggestion: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "RoutineRequest":
        if not (self.text or self.suggestion):
            raise ValueError("Send text or suggestion")
        return self


class ActivityRequest(BaseModel):
    """Body of ``POST /api/v1/activity``: a task the user completed in the secure room."""

    task: str = Field(min_length=3, max_length=300)
    url: str | None = Field(default=None, max_length=2048)
