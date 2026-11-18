"""Insights module: anonymous aggregated analytics."""

from typing import Any

from fastapi import APIRouter

from app.api.dependencies import Events

router = APIRouter(tags=["insights"])


@router.get("/insights/summary")
async def insights_summary(events: Events) -> dict[str, Any]:
    """Blocked-scam counts by kind and region."""
    return await events.summary()
