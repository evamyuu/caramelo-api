"""Knowledge base repositories (retrieval side of RAG).

The corpus is curated public guidance, never user data. MongoDB Atlas embeds
the ``text`` field automatically (Vector Search auto-embedding), so the API
needs no embedding model of its own.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)
COLLECTION = "knowledge_base"
VECTOR_INDEX = "knowledge_vector"
SEED_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "seed.json"
_CANDIDATES_PER_RESULT = 20
_MIN_TOKEN_LENGTH = 4
# Vector search always returns its nearest neighbours, even for off-topic questions.
# Measured with voyage-4-lite on this corpus: relevant top hits score >= 0.71,
# off-topic questions (geography, recipes, football, gibberish) <= 0.63.
MIN_VECTOR_SCORE = 0.67


@dataclass(frozen=True)
class KnowledgeChunk:
    """One self-contained piece of guidance with its source."""

    topic: str
    title: str
    text: str
    source: str


def load_seed() -> list[KnowledgeChunk]:
    """Read the curated corpus shipped with the repository."""
    return [KnowledgeChunk(**item) for item in json.loads(SEED_PATH.read_text(encoding="utf-8"))]


class KnowledgeRepository(Protocol):
    """Retrieval contract."""

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        """Return the chunks most relevant to ``query``, best first."""


def _tokens(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return {word for word in re.findall(r"[a-z0-9]+", plain) if len(word) >= _MIN_TOKEN_LENGTH}


class InMemoryKnowledgeRepository:
    """Keyword-overlap retrieval over the seed corpus, for development and tests."""

    def __init__(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        self._chunks = chunks if chunks is not None else load_seed()

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        wanted = _tokens(query)
        # One shared word is too weak for longer questions ("receita de bolo" vs "receita médica").
        min_overlap = 2 if len(wanted) >= 3 else 1
        scored = [(len(wanted & _tokens(f"{chunk.title} {chunk.text}")), chunk) for chunk in self._chunks]
        ranked = sorted((item for item in scored if item[0] >= min_overlap), key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in ranked[:limit]]


class MongoKnowledgeRepository:
    """Semantic retrieval with Atlas Vector Search (auto-embedded ``text``)."""

    def __init__(self, database: AsyncDatabase) -> None:
        self._collection = database[COLLECTION]

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": VECTOR_INDEX,
                    "path": "text",
                    "query": {"text": query},
                    "numCandidates": limit * _CANDIDATES_PER_RESULT,
                    "limit": limit,
                }
            },
            {"$set": {"score": {"$meta": "vectorSearchScore"}}},
            {"$match": {"score": {"$gte": MIN_VECTOR_SCORE}}},
            {"$project": {"_id": 0, "topic": 1, "title": 1, "text": 1, "source": 1}},
        ]
        cursor = await self._collection.aggregate(pipeline)
        return [KnowledgeChunk(**document) async for document in cursor]

    async def replace_all(self, chunks: list[KnowledgeChunk]) -> int:
        """Replace the corpus (used by ``scripts/seed_knowledge.py``)."""
        await self._collection.delete_many({})
        result = await self._collection.insert_many([chunk.__dict__.copy() for chunk in chunks])
        return len(result.inserted_ids)


class FallbackKnowledgeRepository:
    """Try the primary repository; on failure or no result, use the secondary one.

    Atlas auto-embedding is rate limited on the free tier, so semantic search can
    fail under load. Keyword search over the same corpus keeps answers grounded.
    """

    def __init__(self, primary: KnowledgeRepository, secondary: KnowledgeRepository) -> None:
        self._primary = primary
        self._secondary = secondary

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeChunk]:
        try:
            chunks = await self._primary.search(query, limit)
        except Exception as exc:  # any driver or provider error
            logger.warning("Primary knowledge search failed, using fallback: %s", exc)
            chunks = []
        return chunks or await self._secondary.search(query, limit)
