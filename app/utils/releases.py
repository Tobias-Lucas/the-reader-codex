from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Iterable

from app.utils.dates import WEEKDAYS_PT, normalize_weekday

SCHEDULE_TYPES = ("Sem calendário", "Semanal", "Quinzenal", "Mensal", "Irregular")
PUBLICATION_STATUSES = ("Em lançamento", "Completo", "Em hiato", "Cancelado")


def normalize_release_days(values: Iterable[str] | str | None) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        raw = [part.strip() for part in values.replace(";", ",").split(",")]
    else:
        raw = [str(part).strip() for part in values]
    result: list[str] = []
    for item in raw:
        day = normalize_weekday(item)
        if day in WEEKDAYS_PT and day not in result:
            result.append(day)
    return sorted(result, key=WEEKDAYS_PT.index)


def serialize_release_days(values: Iterable[str] | str | None) -> str:
    return ",".join(normalize_release_days(values))


def release_dates_between(
    schedule_type: str | None,
    release_days: Iterable[str] | str | None,
    release_month_day: int | None,
    release_anchor_date: str | None,
    start: date,
    end: date,
) -> list[date]:
    """Return deterministic release dates in an inclusive range."""
    if end < start:
        return []
    schedule_type = schedule_type or "Sem calendário"
    if schedule_type in ("Sem calendário", "Irregular"):
        return []

    days = normalize_release_days(release_days)
    result: list[date] = []

    if schedule_type == "Semanal":
        indexes = {WEEKDAYS_PT.index(day) for day in days}
        cursor = start
        while cursor <= end:
            if cursor.weekday() in indexes:
                result.append(cursor)
            cursor += timedelta(days=1)
        return result

    if schedule_type == "Quinzenal":
        try:
            anchor = date.fromisoformat(release_anchor_date or "")
        except ValueError:
            return []
        # The anchor is itself a known release. Future/past releases repeat every 14 days.
        delta = (start - anchor).days
        steps = delta // 14
        cursor = anchor + timedelta(days=steps * 14)
        while cursor < start:
            cursor += timedelta(days=14)
        while cursor <= end:
            result.append(cursor)
            cursor += timedelta(days=14)
        return result

    if schedule_type == "Mensal":
        try:
            wanted_day = int(release_month_day or 0)
        except (TypeError, ValueError):
            return []
        if wanted_day < 1 or wanted_day > 31:
            return []
        year, month = start.year, start.month
        while (year, month) <= (end.year, end.month):
            last_day = monthrange(year, month)[1]
            candidate = date(year, month, min(wanted_day, last_day))
            if start <= candidate <= end:
                result.append(candidate)
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
        return result

    return []


def next_release_date(
    schedule_type: str | None,
    release_days: Iterable[str] | str | None,
    release_month_day: int | None,
    release_anchor_date: str | None,
    from_date: date | None = None,
) -> date | None:
    current = from_date or date.today()
    # A 400 day horizon covers monthly and biweekly patterns comfortably.
    dates = release_dates_between(
        schedule_type,
        release_days,
        release_month_day,
        release_anchor_date,
        current,
        current + timedelta(days=400),
    )
    return dates[0] if dates else None


def release_window(
    schedule_type: str | None,
    release_days: Iterable[str] | str | None,
    release_month_day: int | None,
    release_anchor_date: str | None,
    reference: date | None = None,
) -> dict[str, bool]:
    reference = reference or date.today()
    dates = set(
        release_dates_between(
            schedule_type,
            release_days,
            release_month_day,
            release_anchor_date,
            reference - timedelta(days=1),
            reference + timedelta(days=1),
        )
    )
    return {
        "yesterday": reference - timedelta(days=1) in dates,
        "today": reference in dates,
        "tomorrow": reference + timedelta(days=1) in dates,
    }


def release_description(schedule_type: str | None, release_days: str | None, release_month_day: int | None) -> str:
    schedule_type = schedule_type or "Sem calendário"
    if schedule_type == "Semanal":
        days = normalize_release_days(release_days)
        if not days:
            return "Sem dia definido"
        return "Semanal: " + ", ".join(days)
    if schedule_type == "Quinzenal":
        return "A cada 14 dias"
    if schedule_type == "Mensal":
        return f"Todo dia {release_month_day}" if release_month_day else "Mensal"
    if schedule_type == "Irregular":
        return "Lançamento irregular"
    return "Sem calendário"
