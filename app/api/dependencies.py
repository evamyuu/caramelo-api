"""FastAPI dependencies. Routers depend on abstractions, not on concrete storage."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.db.repositories.events import EventRepository


def get_event_repository(request: Request) -> EventRepository:
    return request.app.state.events


Events = Annotated[EventRepository, Depends(get_event_repository)]
