"""FastAPI dependencies. Routers depend on abstractions, not on concrete storage."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.db.repositories.events import EventRepository
from app.db.repositories.knowledge import KnowledgeRepository


def get_event_repository(request: Request) -> EventRepository:
    return request.app.state.events


Events = Annotated[EventRepository, Depends(get_event_repository)]


def get_knowledge_repository(request: Request) -> KnowledgeRepository:
    return request.app.state.knowledge


Knowledge = Annotated[KnowledgeRepository, Depends(get_knowledge_repository)]
