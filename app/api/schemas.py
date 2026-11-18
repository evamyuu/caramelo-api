"""Request models for the HTTP API."""

from pydantic import BaseModel, Field


class LinkScanRequest(BaseModel):
    """Body of ``POST /api/v1/links/scan``."""

    url: str = Field(min_length=3, max_length=2048, examples=["https://example.com"])


class CallAssessmentRequest(BaseModel):
    """Body of ``POST /api/v1/calls/assess``. Keys are defined in ``risk.CALL_SIGNALS``."""

    signals: dict[str, bool]


class ChatRequest(BaseModel):
    """Body of ``POST /api/v1/assistant/chat``."""

    message: str = Field(min_length=1, max_length=1000)
