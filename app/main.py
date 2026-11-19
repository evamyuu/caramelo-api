"""Caramelo API entry point. Run with ``uvicorn app.main:app``."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.db import mongo
from app.db.repositories.events import InMemoryEventRepository, MongoEventRepository
from app.db.repositories.knowledge import (
    FallbackKnowledgeRepository,
    InMemoryKnowledgeRepository,
    MongoKnowledgeRepository,
)

logger = logging.getLogger(__name__)
DEMO_SITES_DIR = Path(__file__).resolve().parent.parent / "demo_sites"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Wire storage at startup and release it at shutdown (composition root)."""
    if not settings.mongodb_uri:
        logger.info("MONGODB_URI not set: using in-memory storage")
        application.state.events = InMemoryEventRepository()
        application.state.knowledge = InMemoryKnowledgeRepository()
        yield
        return
    client = mongo.create_client(settings.mongodb_uri)
    database = mongo.get_database(client, settings.mongodb_database)
    repository = MongoEventRepository(database, settings.event_ttl_days)
    application.state.knowledge = FallbackKnowledgeRepository(
        MongoKnowledgeRepository(database), InMemoryKnowledgeRepository()
    )
    await repository.ensure_indexes()
    application.state.events = repository
    try:
        yield
    finally:
        await client.close()


def create_app() -> FastAPI:
    """Application factory."""
    application = FastAPI(
        title="Caramelo API",
        version="0.1.0",
        description="Backend for Caramelo, a guard-dog assistant that protects older adults on their phones.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )
    application.include_router(api_router)
    # Clearly fictitious pages used by the demo and the end-to-end tests.
    application.mount("/demo", StaticFiles(directory=DEMO_SITES_DIR, html=True), name="demo")
    return application


app = create_app()
