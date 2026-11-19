"""Routine and activity repositories.

The prototype has a single user, so documents carry no user id; a multi-user
deployment adds one field and an index. Activity (tasks completed in the secure
room) is what Caramelo learns routines from; it expires like risk events.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo.asynchronous.database import AsyncDatabase

from app.services.insights import BRAZIL_TZ
from app.services.routines import Routine

ROUTINES = "routines"
ACTIVITY = "activity"


class RoutineRepository(Protocol):
    async def list(self) -> list[Routine]: ...
    async def add(self, routine: Routine) -> Routine: ...
    async def delete(self, routine_id: str) -> bool: ...
    async def mark_done(self, routine_id: str, day: str) -> bool: ...
    async def record_activity(self, task: str, url: str | None, at: datetime | None = None) -> None: ...
    async def activity(self) -> list[dict[str, Any]]: ...


def _with_id(routine: Routine) -> Routine:
    routine.id = routine.id or uuid.uuid4().hex[:12]
    routine.created = routine.created or datetime.now(BRAZIL_TZ).date().isoformat()
    return routine


class InMemoryRoutineRepository:
    def __init__(self) -> None:
        self._routines: dict[str, Routine] = {}
        self._activity: list[dict[str, Any]] = []

    async def list(self) -> list[Routine]:
        return list(self._routines.values())

    async def add(self, routine: Routine) -> Routine:
        routine = _with_id(routine)
        self._routines[routine.id] = routine
        return routine

    async def delete(self, routine_id: str) -> bool:
        return self._routines.pop(routine_id, None) is not None

    async def mark_done(self, routine_id: str, day: str) -> bool:
        routine = self._routines.get(routine_id)
        if routine and day not in routine.done:
            routine.done.append(day)
        return routine is not None

    async def record_activity(self, task: str, url: str | None, at: datetime | None = None) -> None:
        self._activity.append({"task": task, "url": url, "at": at or datetime.now(UTC)})

    async def activity(self) -> list[dict[str, Any]]:
        return list(self._activity)


class MongoRoutineRepository:
    def __init__(self, database: AsyncDatabase, ttl_days: int) -> None:
        self._routines = database[ROUTINES]
        self._activity = database[ACTIVITY]
        self._ttl_seconds = ttl_days * 86_400

    async def ensure_indexes(self) -> None:
        await self._activity.create_index("at", expireAfterSeconds=self._ttl_seconds)

    async def list(self) -> list[Routine]:
        cursor = self._routines.find({}, {"_id": 0})
        return [Routine(**document) async for document in cursor]

    async def add(self, routine: Routine) -> Routine:
        routine = _with_id(routine)
        await self._routines.insert_one(asdict(routine))
        return routine

    async def delete(self, routine_id: str) -> bool:
        return (await self._routines.delete_one({"id": routine_id})).deleted_count == 1

    async def mark_done(self, routine_id: str, day: str) -> bool:
        result = await self._routines.update_one({"id": routine_id}, {"$addToSet": {"done": day}})
        return result.matched_count == 1

    async def record_activity(self, task: str, url: str | None, at: datetime | None = None) -> None:
        await self._activity.insert_one({"task": task, "url": url, "at": at or datetime.now(UTC)})

    async def activity(self) -> list[dict[str, Any]]:
        cursor = self._activity.find({}, {"_id": 0}).sort("at", 1)
        return [{**entry, "at": entry["at"].replace(tzinfo=UTC)} async for entry in cursor]
