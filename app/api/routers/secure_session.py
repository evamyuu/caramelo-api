"""Co-browsing WebSocket. Protocol documented in ``app.services.secure_session``."""

import contextlib

from fastapi import APIRouter, WebSocket

from app.services.secure_session import SecureSession

router = APIRouter(tags=["cobrowse"])


@router.websocket("/secure-session")
async def secure_session(websocket: WebSocket) -> None:
    """First client frame: ``{task, url, scripted_plan?}``."""
    await websocket.accept()
    start = await websocket.receive_json()
    await SecureSession(websocket, start.get("task", ""), start["url"], start.get("scripted_plan")).run()
    with contextlib.suppress(RuntimeError):  # already closed by the client
        await websocket.close()
