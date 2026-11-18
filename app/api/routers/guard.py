"""Guard module: scam protection for links and calls."""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from app import integrations
from app.api.dependencies import Events
from app.api.schemas import CallAssessmentRequest, LinkScanRequest
from app.services import link_scanner, risk

router = APIRouter(tags=["guard"])
_DEMO_PHONE_NUMBER = "+5511999990000"


@router.post("/links/scan")
async def scan_link(body: LinkScanRequest, events: Events) -> dict[str, Any]:
    """Open a link in an isolated browser and return a scam verdict."""
    report = await link_scanner.scan(body.url)
    await events.add("link", report["score"])
    return report


@router.post("/calls/assess")
async def assess_call(body: CallAssessmentRequest, events: Events) -> dict[str, Any]:
    """Score an incoming call from its observed signals."""
    assessment = risk.assess_call(body.signals)
    await events.add("call", assessment.score)
    return {**asdict(assessment), "carrier": integrations.sim_swap_retrieve_date(_DEMO_PHONE_NUMBER)}
