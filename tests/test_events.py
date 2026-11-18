from app.db.repositories.events import InMemoryEventRepository


async def test_summary_counts_only_blocked_events():
    repository = InMemoryEventRepository()
    await repository.add("link", 80)
    await repository.add("call", 92)
    await repository.add("link", 10)
    summary = await repository.summary()
    assert summary == {"total": 3, "blocked": 2, "by_kind": {"link": 1, "call": 1},
                       "by_region": {"SP-capital": 2}}
