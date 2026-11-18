"""Operational endpoints."""

from fastapi import APIRouter

from app.ai import client as llm

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe and active LLM provider."""
    return {"status": "ok", "llm_provider": llm.provider()}
