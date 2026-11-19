"""Operational endpoints."""

from fastapi import APIRouter, Request

from app.ai import client as llm

router = APIRouter(tags=["system"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    """Liveness probe, active LLM provider and where data is stored."""
    return {"status": "ok", "llm_provider": llm.provider(), "storage": getattr(request.app.state, "storage", "unknown")}
