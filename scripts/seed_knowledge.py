"""Load ``app/knowledge/seed.json`` into MongoDB Atlas.

Usage: ``MONGODB_URI=... python -m scripts.seed_knowledge``

The vector index ``knowledge_vector`` (auto-embedding on ``text``) must exist;
see docs/architecture.md.
"""

from __future__ import annotations

import asyncio

from app.config import settings
from app.db import mongo
from app.db.repositories.knowledge import MongoKnowledgeRepository, load_seed


async def main() -> None:
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is not set")
    client = mongo.create_client(settings.mongodb_uri)
    try:
        repository = MongoKnowledgeRepository(mongo.get_database(client, settings.mongodb_database))
        print(f"Inserted {await repository.replace_all(load_seed())} knowledge chunks")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
