"""Companion module: everyday help (balance, free-form questions)."""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from app import integrations
from app.ai import client as llm
from app.api.dependencies import Knowledge
from app.api.schemas import ChatRequest
from app.services import assistant

router = APIRouter(tags=["companion"])


@router.get("/accounts/balance")
def account_balance() -> dict[str, Any]:
    """Account balance and recent transactions (simulated Open Finance)."""
    return integrations.account_balance()


@router.post("/assistant/chat")
async def chat(body: ChatRequest, knowledge: Knowledge) -> dict[str, Any]:
    """Free-form question answered from the curated knowledge base (RAG)."""
    reply = await assistant.answer(body.message, knowledge)
    return {**asdict(reply), "llm_provider": llm.provider()}
