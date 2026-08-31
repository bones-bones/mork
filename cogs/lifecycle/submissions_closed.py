"""US Eastern closed days for #submissions (Tuesday and Saturday)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC
from zoneinfo import ZoneInfo

SUBMISSIONS_TZ = ZoneInfo("America/New_York")
CLOSED_WEEKDAYS = {1, 5}  # Tuesday, Saturday


def _as_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def is_submissions_closed(at: datetime | None = None) -> bool:
    """True for the full local calendar day on closed weekdays in US Eastern."""
    now = _as_aware_utc(at or datetime.now(UTC))
    return now.astimezone(SUBMISSIONS_TZ).weekday() in CLOSED_WEEKDAYS


def elapsed_open_hours(start: datetime, end: datetime | None = None) -> float:
    """Hours between start and end that are not on closed weekdays US Eastern."""
    start_utc = _as_aware_utc(start)
    end_utc = _as_aware_utc(end or datetime.now(UTC))
    if end_utc <= start_utc:
        return 0.0

    open_seconds = 0.0
    cursor = start_utc
    while cursor < end_utc:
        local = cursor.astimezone(SUBMISSIONS_TZ)
        next_midnight_local = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        segment_end = min(end_utc, next_midnight_local.astimezone(UTC))
        if segment_end <= cursor:
            cursor = cursor + timedelta(minutes=1)
            continue
        if local.weekday() not in CLOSED_WEEKDAYS:
            open_seconds += (segment_end - cursor).total_seconds()
        cursor = segment_end
    return open_seconds / 3600
