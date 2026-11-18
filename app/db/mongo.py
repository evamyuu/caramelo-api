"""MongoDB Atlas connection lifecycle.

One client per process (it owns the connection pool), created at startup and
closed at shutdown by the application lifespan.
"""

from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.server_api import ServerApi

APP_NAME = "caramelo-api"
_SERVER_SELECTION_TIMEOUT_MS = 5000


def create_client(uri: str) -> AsyncMongoClient:
    """Create a client pinned to Stable API v1, as Atlas recommends."""
    return AsyncMongoClient(
        uri,
        server_api=ServerApi("1"),
        appname=APP_NAME,
        serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
        retryWrites=True,
    )


def get_database(client: AsyncMongoClient, name: str) -> AsyncDatabase:
    return client[name]
