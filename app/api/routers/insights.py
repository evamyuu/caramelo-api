"""Insights module: anonymous aggregated analytics."""

from typing import Any

from fastapi import APIRouter, Query

from app.api.dependencies import Events
from app.services import insights

router = APIRouter(tags=["insights"])


@router.get("/insights/summary")
async def insights_summary(events: Events) -> dict[str, Any]:
    """Blocked-scam counts by kind and region."""
    return await events.summary()


@router.get("/insights/dashboard")
async def insights_dashboard(events: Events, days: int = Query(30, ge=14, le=90)) -> dict[str, Any]:
    """Partner dashboard: trend, ranking by state, top scam signals and scam waves."""
    return insights.shape_dashboard(await events.raw_stats(days), days)
