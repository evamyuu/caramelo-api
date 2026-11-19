from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.services import routines as service
from app.services.insights import BRAZIL_TZ

# Wednesday 18/11/2026, 14:20 in Brazil.
NOW = datetime(2026, 11, 18, 14, 20, tzinfo=BRAZIL_TZ).astimezone(UTC)


def test_rules_understand_daily_reminders_and_monthly_tasks():
    medicine = service.parse_rules("Me lembra do remédio da pressão às 14h todo dia")
    assert (medicine.kind, medicine.time, medicine.days, medicine.month_day) == ("reminder", "14:00", [], None)

    payment = service.parse_rules("Todo dia 5, vê meu pagamento do INSS")
    assert (payment.kind, payment.month_day, payment.url) == ("task", 5, "https://meu.inss.gov.br/")

    weekly = service.parse_rules("toda segunda e quinta às 8:30 caminhada")
    assert (weekly.time, weekly.days) == ("08:30", [0, 3])

    assert service.parse_rules("remédio") is None  # no time and no day: ask again


def test_model_output_is_validated_and_never_trusted_blindly():
    routine = service.from_model({"title": "Remédio", "kind": "task", "time": "25:00"}, "remédio às 9h")
    assert routine.time == "09:00" and routine.kind == "reminder"  # bad time falls back to the rules
    routine = service.from_model({"title": "x", "kind": "task", "time": "10:00", "url": "http://banco"}, "x às 10h")
    assert routine.kind == "reminder" and routine.url is None  # a task needs an https page
    routine = service.from_model({"title": "INSS", "kind": "task", "time": "10:00", "url": "https://www.gov.br/inss"},
                                 "ver meu pagamento do INSS às 10h")
    assert routine.url == "https://meu.inss.gov.br/"  # the hand-checked page wins


def test_agenda_statuses_and_next_item():
    routines = [
        service.Routine(title="Remédio", kind="reminder", time="14:00", id="a"),
        service.Routine(title="Almoço", kind="reminder", time="12:00", id="b", done=["2026-11-18"]),
        service.Routine(title="Chá", kind="reminder", time="20:00", id="c"),
        service.Routine(title="Feira", kind="reminder", time="09:00", id="d", days=[5]),  # Saturdays only
    ]
    agenda = service.agenda(routines, NOW)
    assert [(i["id"], i["status"]) for i in agenda["items"]] == [("b", "done"), ("a", "due"), ("c", "upcoming")]
    assert agenda["next"]["id"] == "a"


def test_adherence_counts_reminders_taken_on_the_day():
    routine = service.Routine(title="Remédio", kind="reminder", time="08:00", done=["2026-11-18", "2026-11-17"])
    assert service.adherence([routine], NOW) == {"done": 2, "expected": 7}
    routine.created = "2026-11-17"  # created two days ago: only those days count
    assert service.adherence([routine], NOW) == {"done": 2, "expected": 2}


def test_repeated_tasks_become_suggested_routines():
    task = "Ver meu último pagamento do INSS"
    activity = [
        {"task": task, "url": "https://meu.inss.gov.br/", "at": datetime(2026, 9, 5, 13, tzinfo=UTC)},
        {"task": task, "url": "https://meu.inss.gov.br/", "at": datetime(2026, 10, 6, 13, tzinfo=UTC)},
        {"task": "Consultar restituição", "url": None, "at": NOW - timedelta(days=3)},  # only once
    ]
    [suggestion] = service.suggest(activity, [])
    assert (suggestion.month_day, suggestion.time, suggestion.source) == (6, "10:00", "learned")
    assert service.suggest(activity, [suggestion]) == []  # already a routine


def test_routine_api_flow(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    with TestClient(create_app()) as client:
        created = client.post("/api/v1/routines", json={"text": "remédio da pressão às 14h todo dia"}).json()
        assert created["schedule"] == "todo dia às 14:00"
        assert client.post(f"/api/v1/routines/{created['id']}/done").json() == {"done": True}
        listing = client.get("/api/v1/routines").json()
        assert listing["agenda"]["items"][0]["status"] == "done"
        assert client.post("/api/v1/routines", json={"text": "algum dia"}).status_code == 422
        assert client.post("/api/v1/activity", json={"task": "Ver pagamento"}).json() == {"suggestion": None}
