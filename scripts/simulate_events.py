"""Fill the partner dashboard with demonstration events, flagged as simulated.

Usage: ``python -m scripts.simulate_events [--events 600] [--clear]``
(reads ``MONGODB_URI`` from the environment or ``.env``).

Every inserted event has ``simulated: true`` and the dashboard shows the share
of simulated data, so demo numbers are never mistaken for real ones. The mix
roughly follows where older adults live in Brazil, and a "fake bank call" wave
is planted in Pernambuco in the last week to show wave detection.
``--clear`` removes only simulated events.
"""

from __future__ import annotations

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from app.config import settings  # noqa: E402 - settings read the environment loaded above
from app.db import mongo  # noqa: E402
from app.db.repositories.events import COLLECTION, MongoEventRepository, new_event  # noqa: E402

# Approximate share of people aged 60+ per state (IBGE Censo 2022, rounded).
STATE_WEIGHTS = {
    "SP": 22, "MG": 11, "RJ": 10, "BA": 6.5, "RS": 6.5, "PR": 5.5, "PE": 4.5, "CE": 4, "SC": 3.5,
    "GO": 3, "PA": 2.5, "MA": 2.5, "PB": 2, "ES": 2, "RN": 1.7, "AL": 1.4, "PI": 1.5, "MT": 1.3,
    "DF": 1.3, "MS": 1.2, "SE": 1, "AM": 1.2, "RO": 0.6, "TO": 0.6, "AC": 0.3, "AP": 0.2, "RR": 0.2,
}  # fmt: skip
CALL_PATTERNS = [  # (signals, weight)
    (["missing_verified_origin", "asks_for_code_or_password", "claims_bank_or_government", "creates_urgency"], 5),
    (["unknown_caller", "creates_urgency", "asks_for_code_or_password"], 3),
    (["missing_verified_origin", "recent_sim_swap", "asks_for_code_or_password"], 1),
    (["unknown_caller"], 4),  # usually harmless
]
LINK_PATTERNS = [
    (["brand_impersonation", "asks_password", "urgency", "young_domain"], 5),
    (["suspicious_tld", "asks_personal_data", "urgency"], 3),
    (["redirect", "no_https", "auto_download"], 1),
    (["redirect"], 4),  # usually harmless
]
WEIGHTS = {"missing_verified_origin": 25, "unknown_caller": 10, "asks_for_code_or_password": 30,
           "creates_urgency": 15, "claims_bank_or_government": 12, "recent_sim_swap": 20,
           "brand_impersonation": 35, "asks_password": 20, "urgency": 10, "young_domain": 25,
           "suspicious_tld": 15, "asks_personal_data": 15, "redirect": 15, "no_https": 15,
           "auto_download": 30}  # fmt: skip


def _pick(patterns: list[tuple[list[str], int]]) -> list[str]:
    return random.choices([p for p, _ in patterns], weights=[w for _, w in patterns])[0]


def _events(count: int, now: datetime) -> list[tuple[str, int, str, list[str], datetime]]:
    rows = []
    states, weights = list(STATE_WEIGHTS), list(STATE_WEIGHTS.values())
    for _ in range(count):
        kind = random.choice(["call", "link"])
        signals = _pick(CALL_PATTERNS if kind == "call" else LINK_PATTERNS)
        when = now - timedelta(days=random.uniform(0, 30))
        score = min(100, sum(WEIGHTS[s] for s in signals))
        rows.append((kind, score, random.choices(states, weights)[0], signals, when))
    # Planted wave: fake bank calls in Pernambuco during the last week.
    wave = ["missing_verified_origin", "asks_for_code_or_password", "claims_bank_or_government", "creates_urgency"]
    for _ in range(count // 12):
        rows.append(("call", 82, "PE", wave, now - timedelta(days=random.uniform(0, 6.5))))
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--events", type=int, default=600)
    parser.add_argument("--clear", action="store_true", help="only remove simulated events")
    args = parser.parse_args()
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is not set")
    client = mongo.create_client(settings.mongodb_uri)
    try:
        database = mongo.get_database(client, settings.mongodb_database)
        removed = await database[COLLECTION].delete_many({"simulated": True})
        print(f"Removed {removed.deleted_count} simulated events")
        if args.clear:
            return
        repository = MongoEventRepository(database, settings.event_ttl_days)
        await repository.ensure_indexes()
        rows = _events(args.events, datetime.now(UTC))
        await database[COLLECTION].insert_many(
            [new_event(kind, score, state, signals, True, when) for kind, score, state, signals, when in rows]
        )
        print(f"Inserted {len(rows)} simulated events")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
