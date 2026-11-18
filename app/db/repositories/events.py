"""Risk event repositories.

Events are anonymous by design (LGPD data minimisation): no phone number, URL
or user identifier is stored, only the event kind, score and a coarse region.
They feed the aggregated "scam wave" insight.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo.asynchronous.database import AsyncDatabase

from app.services.risk import SCAM_THRESHOLD

DEFAULT_REGION = "SP-capital"
COLLECTION = "risk_events"


class EventRepository(Protocol):
    """Storage contract for risk events."""

    async def add(self, kind: str, score: int, region: str = DEFAULT_REGION) -> None:
        """Persist one event."""

    async def summary(self) -> dict[str, Any]:
        """Return totals and blocked-event counts grouped by kind and region."""


class InMemoryEventRepository:
    """Process-local repository for development and tests."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def add(self, kind: str, score: int, region: str = DEFAULT_REGION) -> None:
        self._events.append({"kind": kind, "score": score, "region": region})

    async def summary(self) -> dict[str, Any]:
        blocked = [e for e in self._events if e["score"] >= SCAM_THRESHOLD]
        return {
            "total": len(self._events),
            "blocked": len(blocked),
            "by_kind": dict(Counter(e["kind"] for e in blocked)),
            "by_region": dict(Counter(e["region"] for e in blocked)),
        }


class MongoEventRepository:
    """MongoDB repository. A TTL index expires events after ``EVENT_TTL_DAYS``."""

    def __init__(self, database: AsyncDatabase, ttl_days: int) -> None:
        self._collection = database[COLLECTION]
        self._ttl_seconds = ttl_days * 86_400

    async def ensure_indexes(self) -> None:
        """Create indexes (idempotent). Called once at startup."""
        await self._collection.create_index("created_at", expireAfterSeconds=self._ttl_seconds)
        # Equality on score range first is not selective; kind/region support the grouped reads.
        await self._collection.create_index([("kind", 1), ("region", 1), ("score", -1)])

    async def add(self, kind: str, score: int, region: str = DEFAULT_REGION) -> None:
        await self._collection.insert_one(
            {"kind": kind, "score": score, "region": region, "created_at": datetime.now(UTC)}
        )

    async def summary(self) -> dict[str, Any]:
        def group(by: str) -> list[dict[str, Any]]:
            return [{"$group": {"_id": f"${by}", "count": {"$sum": 1}}}]

        pipeline = [
            {
                "$facet": {
                    "total": [{"$count": "n"}],
                    "blocked": [{"$match": {"score": {"$gte": SCAM_THRESHOLD}}}, {"$count": "n"}],
                    "by_kind": [{"$match": {"score": {"$gte": SCAM_THRESHOLD}}}, *group("kind")],
                    "by_region": [{"$match": {"score": {"$gte": SCAM_THRESHOLD}}}, *group("region")],
                }
            }
        ]
        cursor = await self._collection.aggregate(pipeline)
        result = (await cursor.to_list(1))[0]

        def count(key: str) -> int:
            return result[key][0]["n"] if result[key] else 0

        return {
            "total": count("total"),
            "blocked": count("blocked"),
            "by_kind": {row["_id"]: row["count"] for row in result["by_kind"]},
            "by_region": {row["_id"]: row["count"] for row in result["by_region"]},
        }
