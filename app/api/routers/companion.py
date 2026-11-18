"""Companion module: everyday help (balance, free-form questions)."""

from typing import Any

from fastapi import APIRouter

from app import integrations
from app.ai import client as llm
from app.api.schemas import ChatRequest

router = APIRouter(tags=["companion"])
_NO_LLM_REPLY = (
    "Ainda estou sem a minha IA ligada. Posso checar um link, fazer uma tarefa junto, "
    "guiar a selfie ou ler um remédio."
)


@router.get("/accounts/balance")
def account_balance() -> dict[str, Any]:
    """Account balance and recent transactions (simulated Open Finance)."""
    return integrations.account_balance()


@router.post("/assistant/chat")
async def chat(body: ChatRequest) -> dict[str, str]:
    """Free-form question answered by the assistant persona."""
    reply = await llm.complete(body.message)
    return {"speech": reply or _NO_LLM_REPLY, "llm_provider": llm.provider()}
