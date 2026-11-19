"""Scam analytics for partners (carrier, CiX, Febraban).

Turns anonymous risk events into a dashboard: trend per day, ranking by state,
most frequent scam signals and "waves", i.e. states where blocked scams grew
sharply in the last week. Events hold no phone number, URL or user id, only the
kind, score, state, signal keys and time (LGPD data minimisation).

Repositories aggregate raw counts (``RawStats``); :func:`shape_dashboard` is the
single, pure place where those counts become the dashboard.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, TypedDict

from app.services.risk import CALL_SIGNALS

BRAZIL_TZ = timezone(timedelta(hours=-3))  # Brazil has no daylight saving time since 2019
UFS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
)  # fmt: skip
UNKNOWN_REGION = "ND"
WAVE_WINDOW_DAYS = 7
WAVE_MIN_EVENTS = 8  # below this, week-to-week changes are noise
WAVE_GROWTH = 2.0
TOP_SIGNALS = 6

LINK_SIGNAL_LABELS = {
    "redirect": "Link que leva para outro endereço",
    "no_https": "Site sem cadeado (https)",
    "ip_address": "Endereço que é só um número",
    "lookalike_letters": "Endereço com letras disfarçadas",
    "suspicious_tld": "Final de endereço comum em golpes",
    "odd_address": "Endereço comprido e estranho",
    "brand_impersonation": "Usa nome de marca em endereço não oficial",
    "asks_password": "Pede senha",
    "asks_personal_data": "Pede dados pessoais",
    "urgency": "Pressa e ameaça",
    "auto_download": "Tenta baixar arquivo sozinho",
    "young_domain": "Site criado há poucos dias",
    "unreachable": "Link que não abre",
}
SIGNAL_LABELS = {**LINK_SIGNAL_LABELS, **{key: signal.label for key, signal in CALL_SIGNALS.items()}}


class RegionCounts(TypedDict):
    total: int
    blocked: int
    last7: int  # blocked in the last WAVE_WINDOW_DAYS
    prev7: int  # blocked in the window before that


class RawStats(TypedDict):
    total: int
    blocked: int
    simulated: int
    score_sum_blocked: int
    by_kind: dict[str, int]
    by_region: dict[str, RegionCounts]
    by_day: dict[str, int]  # "YYYY-MM-DD" (Brazil time) -> blocked
    signals: dict[str, int]  # signal key -> blocked events showing it


def normalize_region(region: str | None) -> str:
    """A Brazilian state code, or ``ND`` when unknown. Accepts ``"SP-capital"`` style values."""
    code = (region or "").split("-")[0].strip().upper()
    return code if code in UFS else UNKNOWN_REGION


def window_starts(now: datetime) -> tuple[datetime, datetime]:
    """Start of the last wave window and of the one before it."""
    last = now - timedelta(days=WAVE_WINDOW_DAYS)
    return last, last - timedelta(days=WAVE_WINDOW_DAYS)


def day_key(moment: datetime) -> str:
    return moment.astimezone(BRAZIL_TZ).strftime("%Y-%m-%d")


def shape_dashboard(raw: RawStats, days: int, now: datetime | None = None) -> dict[str, Any]:
    """Build the partner dashboard from aggregated counts."""
    now = now or datetime.now(UTC)
    by_day = [
        {"date": (key := day_key(now - timedelta(days=offset))), "blocked": raw["by_day"].get(key, 0)}
        for offset in range(days - 1, -1, -1)
    ]
    regions: dict[str, RegionCounts] = {}
    for region, counts in raw["by_region"].items():  # merge legacy values such as "SP-capital"
        merged = regions.setdefault(normalize_region(region), {"total": 0, "blocked": 0, "last7": 0, "prev7": 0})
        for field in merged:
            merged[field] += counts[field]  # type: ignore[literal-required]
    by_region = sorted(
        ({"region": region, **counts} for region, counts in regions.items()),
        key=lambda row: (row["blocked"], row["total"]),
        reverse=True,
    )
    waves = [
        {
            "region": row["region"],
            "last7": row["last7"],
            "prev7": row["prev7"],
            "growth": round(row["last7"] / max(row["prev7"], 1), 1),
        }
        for row in by_region
        if row["region"] != UNKNOWN_REGION
        and row["last7"] >= WAVE_MIN_EVENTS
        and row["last7"] >= WAVE_GROWTH * max(row["prev7"], 1)
    ]
    top_signals = sorted(raw["signals"].items(), key=lambda item: item[1], reverse=True)[:TOP_SIGNALS]
    blocked = raw["blocked"]
    return {
        "period_days": days,
        "generated_at": now.isoformat(),
        "total": raw["total"],
        "blocked": blocked,
        "block_rate": round(blocked / raw["total"], 3) if raw["total"] else 0.0,
        "avg_blocked_score": round(raw["score_sum_blocked"] / blocked) if blocked else 0,
        "simulated_share": round(raw["simulated"] / raw["total"], 3) if raw["total"] else 0.0,
        "by_kind": raw["by_kind"],
        "by_region": by_region,
        "by_day": by_day,
        "top_signals": [
            {"signal": key, "label": SIGNAL_LABELS.get(key, key), "count": count} for key, count in top_signals
        ],
        "waves": sorted(waves, key=lambda wave: wave["growth"], reverse=True),
    }
