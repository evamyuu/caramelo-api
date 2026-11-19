from datetime import UTC, datetime, timedelta

from app.db.repositories.events import InMemoryEventRepository
from app.services import insights

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)


async def _dashboard(repository: InMemoryEventRepository, days: int = 30) -> dict:
    return insights.shape_dashboard(await repository.raw_stats(days, NOW), days, NOW)


async def test_dashboard_counts_trend_regions_and_signals():
    repository = InMemoryEventRepository()
    await repository.add("call", 82, "sp", ["asks_for_code_or_password", "creates_urgency"], created_at=NOW)
    await repository.add("link", 90, "RJ", ["brand_impersonation", "asks_password"], created_at=NOW - timedelta(days=2))
    await repository.add("link", 15, "RJ", ["redirect"], created_at=NOW - timedelta(days=3))  # not blocked
    await repository.add("call", 80, "SP", ["asks_for_code_or_password"], created_at=NOW - timedelta(days=40))  # old

    dashboard = await _dashboard(repository)

    assert (dashboard["total"], dashboard["blocked"]) == (3, 2)
    assert dashboard["by_kind"] == {"call": 1, "link": 1}
    assert {row["region"]: row["blocked"] for row in dashboard["by_region"]} == {"SP": 1, "RJ": 1}
    assert len(dashboard["by_day"]) == 30 and dashboard["by_day"][-1] == {"date": "2026-11-18", "blocked": 1}
    signals = {row["signal"]: (row["label"], row["count"]) for row in dashboard["top_signals"]}
    assert signals["asks_for_code_or_password"] == ("Pede código ou senha", 1)
    assert "redirect" not in signals  # only blocked events count


async def test_a_sharp_rise_in_a_state_is_flagged_as_a_wave():
    repository = InMemoryEventRepository()
    for hour in range(0, 160, 16):  # 10 blocked in Pernambuco this week, 1 the week before
        await repository.add("call", 82, "PE", ["claims_bank_or_government"], created_at=NOW - timedelta(hours=hour))
    await repository.add("call", 82, "PE", ["claims_bank_or_government"], created_at=NOW - timedelta(days=10))
    for hour in range(0, 336, 12):  # steady activity in São Paulo (14 a week) is not a wave
        await repository.add("call", 82, "SP", [], created_at=NOW - timedelta(hours=hour))

    waves = (await _dashboard(repository))["waves"]

    assert waves == [{"region": "PE", "last7": 10, "prev7": 1, "growth": 10.0}]


async def test_simulated_share_and_unknown_or_legacy_regions():
    repository = InMemoryEventRepository()
    await repository.add("link", 90, "SP-capital", created_at=NOW)
    await repository.add("link", 90, None, simulated=True, created_at=NOW)

    dashboard = await _dashboard(repository)

    assert dashboard["simulated_share"] == 0.5
    assert {row["region"] for row in dashboard["by_region"]} == {"SP", "ND"}
