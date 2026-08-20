"""Smoke tests for #submissions closed days (no Discord)."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cogs.lifecycle.submissions_closed import (
    elapsed_open_hours,
    is_submissions_closed,
)
from cogs.lifecycle.submissions_gates import (
    GATES_CLOSED_MESSAGE,
    GATES_OPENED_MESSAGE,
    gate_announcement_for,
)

NY = ZoneInfo("America/New_York")


def test_closed_weekdays():
    assert is_submissions_closed(datetime(2026, 8, 18, 15, 0, tzinfo=NY))  # Tuesday
    assert is_submissions_closed(datetime(2026, 8, 20, 15, 0, tzinfo=NY))  # Thursday
    assert is_submissions_closed(datetime(2026, 8, 15, 0, 0, tzinfo=NY))  # Saturday
    assert is_submissions_closed(datetime(2026, 8, 15, 23, 59, tzinfo=NY))
    assert not is_submissions_closed(datetime(2026, 8, 17, 15, 0, tzinfo=NY))  # Monday
    assert not is_submissions_closed(datetime(2026, 8, 19, 15, 0, tzinfo=NY))  # Wednesday
    assert not is_submissions_closed(datetime(2026, 8, 16, 12, 0, tzinfo=NY))  # Sunday


def test_closed_uses_eastern_not_utc():
    # 03:00 UTC Tue = 23:00 EDT Mon. 04:30 UTC Tue = 00:30 EDT Tue.
    assert not is_submissions_closed(datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc))
    assert is_submissions_closed(datetime(2026, 8, 18, 4, 30, tzinfo=timezone.utc))


def test_elapsed_skips_saturday():
    start = datetime(2026, 8, 14, 23, 0, tzinfo=NY)  # Friday
    end = datetime(2026, 8, 16, 1, 0, tzinfo=NY)  # Sunday
    assert elapsed_open_hours(start, end) == 2.0


def test_elapsed_skips_tuesday_for_cooldown():
    start = datetime(2026, 8, 17, 10, 0, tzinfo=NY)  # Monday
    still_waiting = datetime(2026, 8, 18, 8, 0, tzinfo=NY)  # Tuesday
    assert elapsed_open_hours(start, still_waiting) == 14.0
    done = datetime(2026, 8, 19, 8, 0, tzinfo=NY)  # Wednesday
    assert elapsed_open_hours(start, done) == 22.0


def test_elapsed_open_weekday_is_wall_clock():
    start = datetime(2026, 8, 17, 10, 0, tzinfo=NY)
    end = datetime(2026, 8, 17, 12, 0, tzinfo=NY)
    assert elapsed_open_hours(start, end) == 2.0


def test_elapsed_zero_when_end_before_start():
    start = datetime(2026, 8, 17, 12, 0, tzinfo=NY)
    end = datetime(2026, 8, 17, 10, 0, tzinfo=NY)
    assert elapsed_open_hours(start, end) == 0.0


def test_gate_announcements():
    tue = datetime(2026, 8, 18, 12, 0, tzinfo=NY)
    thu = datetime(2026, 8, 20, 12, 0, tzinfo=NY)
    sat = datetime(2026, 8, 15, 12, 0, tzinfo=NY)
    wed = datetime(2026, 8, 19, 12, 0, tzinfo=NY)
    fri = datetime(2026, 8, 21, 12, 0, tzinfo=NY)
    sun = datetime(2026, 8, 16, 12, 0, tzinfo=NY)
    mon = datetime(2026, 8, 17, 12, 0, tzinfo=NY)

    assert gate_announcement_for(tue) == GATES_CLOSED_MESSAGE
    assert gate_announcement_for(thu) == GATES_CLOSED_MESSAGE
    assert gate_announcement_for(sat) == GATES_CLOSED_MESSAGE
    assert gate_announcement_for(wed) == GATES_OPENED_MESSAGE
    assert gate_announcement_for(fri) == GATES_OPENED_MESSAGE
    assert gate_announcement_for(sun) == GATES_OPENED_MESSAGE
    assert gate_announcement_for(mon) is None


if __name__ == "__main__":
    test_closed_weekdays()
    test_closed_uses_eastern_not_utc()
    test_elapsed_skips_saturday()
    test_elapsed_skips_tuesday_for_cooldown()
    test_elapsed_open_weekday_is_wall_clock()
    test_elapsed_zero_when_end_before_start()
    test_gate_announcements()
    print("ok")
