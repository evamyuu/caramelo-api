"""Routines: scheduled reminders and tasks Caramelo starts on its own.

Like a scheduled agent run: the user says once, in plain words, what should
happen and when ("todo dia 5, vê meu pagamento do INSS", "me lembra do remédio
da pressão às 14h"), and at that time Caramelo takes the initiative: it reminds,
or offers to do the task together with one tap. Consent and the credential
handover still apply to every task it runs.

Caramelo also learns: when the user does the same task by hand on a regular
day or weekday, it suggests turning it into a routine (:func:`suggest`).
Everything here is pure; storage and the model live elsewhere.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from app.services.insights import BRAZIL_TZ

Kind = Literal["reminder", "task"]
DUE_WINDOW = timedelta(minutes=60)  # after this, a pending item counts as late
LEARN_MIN_REPEATS = 2
WEEKDAYS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
WEEKDAY_NAMES = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
# Words that make a request a task Caramelo can do in the secure room, with its starting page.
TASK_SITES = {
    "inss": "https://meu.inss.gov.br/",
    "aposentadoria": "https://meu.inss.gov.br/",
    "beneficio": "https://meu.inss.gov.br/",
    "restituicao": "https://www.gov.br/receitafederal/",
    "imposto": "https://www.gov.br/receitafederal/",
    "vacina": "https://meususdigital.saude.gov.br/",
    "consulta": "https://meususdigital.saude.gov.br/",
}


@dataclass
class Routine:
    title: str
    kind: Kind
    time: str  # "HH:MM", Brazil time
    days: list[int] = field(default_factory=list)  # weekdays, 0 = Monday; empty with no month_day = every day
    month_day: int | None = None
    task: str | None = None  # what to do in the secure room, for kind == "task"
    url: str | None = None
    source: Literal["user", "learned"] = "user"
    done: list[str] = field(default_factory=list)  # ISO dates on which it was done
    id: str = ""
    created: str = ""  # ISO date; adherence is only counted from this day on


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def _clean_time(hour: int, minute: int) -> str | None:
    return f"{hour:02d}:{minute:02d}" if 0 <= hour < 24 and 0 <= minute < 60 else None


def parse_rules(text: str) -> Routine | None:
    """Understand a routine request without a model. ``None`` when no time is found."""
    plain = _plain(text)
    match = re.search(r"\b(\d{1,2})\s*(?:h|:|horas?)\s*(\d{2})?", plain)
    if match:
        clock = _clean_time(int(match.group(1)), int(match.group(2) or 0))
    elif "meio-dia" in plain or "meio dia" in plain:
        clock = "12:00"
    elif "de manha" in plain:
        clock = "09:00"
    elif "de tarde" in plain or "a tarde" in plain:
        clock = "15:00"
    elif "de noite" in plain or "a noite" in plain:
        clock = "20:00"
    else:
        clock = None
    month_day = re.search(r"\bdia (\d{1,2})\b", plain)
    days = [number for name, number in WEEKDAYS.items() if name in plain]
    if not clock:
        if not (month_day or days):
            return None
        clock = "09:00"  # a day without a time: start of the morning
    site = next((url for word, url in TASK_SITES.items() if word in plain), None)
    title = re.sub(r"^(me lembr\w* (de|do|da)?|caramelo,?|todo dia \d{1,2},?)\s*", "", text.strip(), flags=re.I)
    return Routine(
        title=(title or text).strip().rstrip(".")[:80],
        kind="task" if site else "reminder",
        time=clock,
        days=[] if month_day else days,
        month_day=int(month_day.group(1)) if month_day and 1 <= int(month_day.group(1)) <= 31 else None,
        task=text.strip() if site else None,
        url=site,
    )


def from_model(data: dict[str, Any] | None, text: str) -> Routine | None:
    """Validate a model's routine proposal; anything malformed falls back to the rules."""
    if not data:
        return parse_rules(text)
    clock = data.get("time")
    valid_clock = isinstance(clock, str) and re.fullmatch(r"\d{2}:\d{2}", clock)
    if not valid_clock or not _clean_time(*map(int, clock.split(":"))):
        return parse_rules(text)
    rules = parse_rules(text)
    model_url = data.get("url") if isinstance(data.get("url"), str) and data["url"].startswith("https://") else None
    url = (rules.url if rules else None) or model_url  # hand-checked service pages win over the model's guess
    month_day = data.get("month_day")
    return Routine(
        title=str(data.get("title") or text).strip()[:80],
        kind="task" if data.get("kind") == "task" and url else "reminder",
        time=clock,
        days=sorted({d for d in data.get("days") or [] if isinstance(d, int) and 0 <= d <= 6}),
        month_day=month_day if isinstance(month_day, int) and 1 <= month_day <= 31 else None,
        task=str(data.get("task") or text) if url else None,
        url=url,
    )


def occurs_on(routine: Routine, day: date) -> bool:
    if routine.month_day:
        return day.day == routine.month_day
    return not routine.days or day.weekday() in routine.days


def describe_schedule(routine: Routine) -> str:
    """Short Portuguese description, e.g. "todo dia 5 às 09:00"."""
    if routine.month_day:
        when = f"todo dia {routine.month_day}"
    elif routine.days and len(routine.days) < 7:
        when = "toda " + ", ".join(WEEKDAY_NAMES[d] for d in routine.days)
    else:
        when = "todo dia"
    return f"{when} às {routine.time}"


def agenda(routines: list[Routine], now: datetime) -> dict[str, Any]:
    """Today's items in time order, each with a status, plus the next pending one."""
    local = now.astimezone(BRAZIL_TZ)
    today = local.date()
    items = []
    for routine in routines:
        if not occurs_on(routine, today):
            continue
        at = datetime.combine(today, time.fromisoformat(routine.time), BRAZIL_TZ)
        if today.isoformat() in routine.done:
            status = "done"
        elif local < at:
            status = "upcoming"
        else:
            status = "due" if local - at <= DUE_WINDOW else "late"
        items.append({"id": routine.id, "title": routine.title, "kind": routine.kind, "time": routine.time,
                      "status": status, "task": routine.task, "url": routine.url})  # fmt: skip
    items.sort(key=lambda item: item["time"])
    pending = [item for item in items if item["status"] != "done"]
    return {"date": today.isoformat(), "items": items, "next": pending[0] if pending else None}


def adherence(routines: list[Routine], now: datetime, days: int = 7) -> dict[str, int]:
    """Reminders done on the day they were due, over the last ``days`` days (today included)."""
    today = now.astimezone(BRAZIL_TZ).date()
    expected = done = 0
    for offset in range(days):
        day = today - timedelta(days=offset)
        for routine in routines:
            if routine.created and day.isoformat() < routine.created:
                continue
            if routine.kind == "reminder" and occurs_on(routine, day):
                expected += 1
                done += day.isoformat() in routine.done
    return {"done": done, "expected": expected}


def suggest(activity: list[dict[str, Any]], routines: list[Routine]) -> list[Routine]:
    """Learn routines from tasks the user repeats by hand.

    ``activity`` holds ``{"task", "url", "at"}`` entries for tasks completed in the
    secure room. A task done at least twice around the same day of the month (or
    on the same weekday) becomes a suggestion, unless a routine already covers it.
    """
    covered = {_plain(r.task or r.title) for r in routines}
    by_task: dict[str, list[dict[str, Any]]] = {}
    for entry in activity:
        by_task.setdefault(_plain(entry["task"]), []).append(entry)
    suggestions = []
    for key, entries in by_task.items():
        if key in covered or len(entries) < LEARN_MIN_REPEATS:
            continue
        moments = [entry["at"].astimezone(BRAZIL_TZ) for entry in entries]
        hour = round(statistics.median(m.hour for m in moments))
        month_days = [m.day for m in moments]
        weekdays = {m.weekday() for m in moments}
        routine = Routine(title=entries[-1]["task"], kind="task", time=f"{hour:02d}:00", task=entries[-1]["task"],
                          url=entries[-1].get("url"), source="learned")  # fmt: skip
        if max(month_days) - min(month_days) <= 3:
            routine.month_day = round(statistics.median(month_days))
        elif len(weekdays) == 1:
            routine.days = list(weekdays)
        else:
            continue
        suggestions.append(routine)
    return suggestions
