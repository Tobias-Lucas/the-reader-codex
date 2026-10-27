from __future__ import annotations

from datetime import date, datetime, timedelta
import unicodedata

WEEKDAYS_PT = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)


def iso_to_br(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value)


def br_to_iso(value: str | None, field_name: str = "Data") -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    # Accept the displayed Brazilian format and ISO for compatibility with old input.
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"{field_name} deve estar no formato DD/MM/AAAA.")


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold().strip()


def normalize_weekday(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    folded = _fold(value).replace("-feira", "").strip()
    aliases = {
        "segunda": WEEKDAYS_PT[0],
        "terca": WEEKDAYS_PT[1],
        "quarta": WEEKDAYS_PT[2],
        "quinta": WEEKDAYS_PT[3],
        "sexta": WEEKDAYS_PT[4],
        "sabado": WEEKDAYS_PT[5],
        "domingo": WEEKDAYS_PT[6],
    }
    if folded in aliases:
        return aliases[folded]
    # Preserve unknown legacy text rather than losing data.
    return value


def next_weekday_date(weekday: str | None, from_date: date | None = None) -> date | None:
    normalized = normalize_weekday(weekday)
    if normalized not in WEEKDAYS_PT:
        return None
    current = from_date or date.today()
    target = WEEKDAYS_PT.index(normalized)
    days_ahead = (target - current.weekday()) % 7
    return current + timedelta(days=days_ahead)


def next_release_label(weekday: str | None, from_date: date | None = None) -> str:
    normalized = normalize_weekday(weekday)
    target = next_weekday_date(normalized, from_date=from_date)
    if target is None:
        return ""
    current = from_date or date.today()
    prefix = "Hoje" if target == current else normalized
    return f"{prefix}, {target.strftime('%d/%m/%Y')}"
