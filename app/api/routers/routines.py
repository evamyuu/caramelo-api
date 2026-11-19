"""Routine module: scheduled reminders and tasks, and routines learned from use."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from app.ai import client as llm
from app.ai import prompts
from app.api.dependencies import Routines
from app.api.schemas import ActivityRequest, RoutineRequest
from app.services import routines as service
from app.services.insights import BRAZIL_TZ
from app.services.secure_session import is_blocked

router = APIRouter(tags=["routines"])


def _out(routine: service.Routine) -> dict[str, Any]:
    return {**asdict(routine), "schedule": service.describe_schedule(routine)}


@router.get("/routines")
async def list_routines(repository: Routines) -> dict[str, Any]:
    """Routines, today's agenda, reminder adherence over 7 days and learned suggestions."""
    routines = await repository.list()
    now = datetime.now(UTC)
    return {
        "routines": [_out(r) for r in routines],
        "agenda": service.agenda(routines, now),
        "adherence": service.adherence(routines, now),
        "suggestions": [_out(r) for r in service.suggest(await repository.activity(), routines)],
    }


@router.post("/routines")
async def create_routine(body: RoutineRequest, repository: Routines) -> dict[str, Any]:
    """Create a routine from what the user said (model first, rules as fallback) or from a suggestion."""
    if body.suggestion:
        fields = {k: v for k, v in body.suggestion.items() if k in service.Routine.__dataclass_fields__}
        routine = service.Routine(**{**fields, "id": "", "created": "", "done": [], "source": "learned"})
    else:
        today = datetime.now(BRAZIL_TZ).strftime("%A, %d/%m/%Y")
        reply = await llm.complete(prompts.routine_from_request(body.text or "", today), json_output=True)
        routine = service.from_model(llm.parse_json(reply), body.text or "")
    if routine is None:
        raise HTTPException(422, "Não entendi quando. Diga, por exemplo: “todo dia às 14h, remédio da pressão”.")
    if routine.url and is_blocked(routine.url):  # same rule as the secure room: never a bank
        routine.kind, routine.task, routine.url = "reminder", None, None
    return _out(await repository.add(routine))


@router.delete("/routines/{routine_id}")
async def delete_routine(routine_id: str, repository: Routines) -> dict[str, bool]:
    if not await repository.delete(routine_id):
        raise HTTPException(404, "Rotina não encontrada")
    return {"deleted": True}


@router.post("/routines/{routine_id}/done")
async def complete_routine(routine_id: str, repository: Routines) -> dict[str, bool]:
    """Mark today's occurrence as done (medicine taken, task finished)."""
    if not await repository.mark_done(routine_id, datetime.now(BRAZIL_TZ).date().isoformat()):
        raise HTTPException(404, "Rotina não encontrada")
    return {"done": True}


@router.post("/activity")
async def record_activity(body: ActivityRequest, repository: Routines) -> dict[str, Any]:
    """Record a task completed in the secure room; returns a routine suggestion when one is learned."""
    await repository.record_activity(body.task, body.url)
    routines = await repository.list()
    learned = [s for s in service.suggest(await repository.activity(), routines) if s.task == body.task]
    return {"suggestion": _out(learned[0]) if learned else None}
