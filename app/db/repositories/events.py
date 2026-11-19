"""Risk event repositories.

Events are anonymous by design (LGPD data minimisation): no phone number, URL
or user identifier is stored, only the event kind, score, state (UF), the keys
of the scam signals observed and the time. They feed the partner dashboard
(``app/services/insights.py``).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from pymongo.asynchronous.database import AsyncDatabase

from app.services.insights import RawStats, day_key, normalize_region, window_starts
from app.services.risk import SCAM_THRESHOLD

COLLECTION = "risk_events"


class EventRepository(Protocol):
    """Storage contract for risk events."""

    async def add(
        self, kind: str, score: int, region: str | None = None, signals: list[str] | None = None,
        *, simulated: bool = False, created_at: datetime | None = None,
    ) -> None:  # fmt: skip
        """Persist one event."""

    async def summary(self) -> dict[str, Any]:
        """Return totals and blocked-event counts grouped by kind and region."""

    async def raw_stats(self, days: int, now: datetime | None = None) -> RawStats:
        """Aggregated counts of the last ``days`` days for the dashboard."""


def new_event(
    kind: str, score: int, region: str | None, signals: list[str] | None, simulated: bool, created_at: datetime | None
) -> dict[str, Any]:
    return {
        "kind": kind,
        "score": score,
        "region": normalize_region(region),
        "signals": list(signals or []),
        "simulated": simulated,
        "created_at": created_at or datetime.now(UTC),
    }


class InMemoryEventRepository:
    """Process-local repository for development and tests."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    async def add(
        self, kind: str, score: int, region: str | None = None, signals: list[str] | None = None,
        *, simulated: bool = False, created_at: datetime | None = None,
    ) -> None:  # fmt: skip
        self._events.append(new_event(kind, score, region, signals, simulated, created_at))

    async def summary(self) -> dict[str, Any]:
        blocked = [e for e in self._events if e["score"] >= SCAM_THRESHOLD]
        return {
            "total": len(self._events),
            "blocked": len(blocked),
            "by_kind": dict(Counter(e["kind"] for e in blocked)),
            "by_region": dict(Counter(e["region"] for e in blocked)),
        }

    async def raw_stats(self, days: int, now: datetime | None = None) -> RawStats:
        now = now or datetime.now(UTC)
        last7, prev7 = window_starts(now)
        events = [e for e in self._events if e["created_at"] >= now - timedelta(days=days)]
        blocked = [e for e in events if e["score"] >= SCAM_THRESHOLD]
        regions: dict[str, Any] = {}
        for e in events:
            row = regions.setdefault(e["region"], {"total": 0, "blocked": 0, "last7": 0, "prev7": 0})
            row["total"] += 1
            if e["score"] >= SCAM_THRESHOLD:
                row["blocked"] += 1
                row["last7"] += e["created_at"] >= last7
                row["prev7"] += prev7 <= e["created_at"] < last7
        return {
            "total": len(events),
            "blocked": len(blocked),
            "simulated": sum(e["simulated"] for e in events),
            "score_sum_blocked": sum(e["score"] for e in blocked),
            "by_kind": dict(Counter(e["kind"] for e in blocked)),
            "by_region": regions,
            "by_day": dict(Counter(day_key(e["created_at"]) for e in blocked)),
            "signals": dict(Counter(signal for e in blocked for signal in e["signals"])),
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

    async def add(
        self, kind: str, score: int, region: str | None = None, signals: list[str] | None = None,
        *, simulated: bool = False, created_at: datetime | None = None,
    ) -> None:  # fmt: skip
        await self._collection.insert_one(new_event(kind, score, region, signals, simulated, created_at))

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

    async def raw_stats(self, days: int, now: datetime | None = None) -> RawStats:
        now = now or datetime.now(UTC)
        last7, prev7 = window_starts(now)
        is_blocked = {"$gte": ["$score", SCAM_THRESHOLD]}

        def blocked_between(start: datetime, end: datetime | None = None) -> dict[str, Any]:
            window = [is_blocked, {"$gte": ["$created_at", start]}]
            if end is not None:
                window.append({"$lt": ["$created_at", end]})
            return {"$sum": {"$cond": [{"$and": window}, 1, 0]}}

        only_blocked = {"$match": {"score": {"$gte": SCAM_THRESHOLD}}}
        pipeline = [
            {"$match": {"created_at": {"$gte": now - timedelta(days=days)}}},
            {
                "$facet": {
                    "totals": [{"$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "blocked": {"$sum": {"$cond": [is_blocked, 1, 0]}},
                        "simulated": {"$sum": {"$cond": [{"$eq": ["$simulated", True]}, 1, 0]}},
                        "score_sum_blocked": {"$sum": {"$cond": [is_blocked, "$score", 0]}},
                    }}],
                    "by_kind": [only_blocked, {"$group": {"_id": "$kind", "n": {"$sum": 1}}}],
                    "by_region": [{"$group": {
                        "_id": "$region",
                        "total": {"$sum": 1},
                        "blocked": {"$sum": {"$cond": [is_blocked, 1, 0]}},
                        "last7": blocked_between(last7),
                        "prev7": blocked_between(prev7, last7),
                    }}],
                    "by_day": [only_blocked, {"$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at", "timezone": "-03:00"}},
                        "n": {"$sum": 1},
                    }}],
                    "signals": [
                        only_blocked, {"$unwind": "$signals"}, {"$group": {"_id": "$signals", "n": {"$sum": 1}}},
                    ],
                }
            },
        ]  # fmt: skip
        cursor = await self._collection.aggregate(pipeline)
        result = (await cursor.to_list(1))[0]
        totals = result["totals"][0] if result["totals"] else {}
        return {
            "total": totals.get("total", 0),
            "blocked": totals.get("blocked", 0),
            "simulated": totals.get("simulated", 0),
            "score_sum_blocked": totals.get("score_sum_blocked", 0),
            "by_kind": {row["_id"]: row["n"] for row in result["by_kind"]},
            "by_region": {
                row["_id"]: {key: row[key] for key in ("total", "blocked", "last7", "prev7")}
                for row in result["by_region"]
            },
            "by_day": {row["_id"]: row["n"] for row in result["by_day"]},
            "signals": {row["_id"]: row["n"] for row in result["signals"]},
        }
