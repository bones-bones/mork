"""Smoke tests for submissions day marker helpers (no Discord)."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hc_constants  # noqa: E402
from cogs.lifecycle.submissions_day_markers import (  # noqa: E402
    day_marker_content,
    day_marker_iso_date,
    format_previous_week_body,
    is_submissions_day_marker,
)


def _msg(content: str, author_id: int = hc_constants.MORK_2):
    return SimpleNamespace(content=content, author=SimpleNamespace(id=author_id), jump_url="https://example/jump")


def test_day_marker_content():
    day = datetime(2026, 5, 31, tzinfo=timezone.utc)
    text = day_marker_content(day)
    assert text.startswith(hc_constants.SUBMISSIONS_DAY_MARKER_PREFIX + "2026-05-31")
    assert "Sunday, May 31, 2026" in text


def test_is_and_parse_marker():
    m = _msg(day_marker_content(datetime(2026, 6, 1, tzinfo=timezone.utc)))
    assert is_submissions_day_marker(m)
    assert day_marker_iso_date(m) == "2026-06-01"
    assert not is_submissions_day_marker(_msg("poll", author_id=hc_constants.MORK))


def test_previous_week_body():
    markers = [
        _msg(day_marker_content(datetime(2026, 5, 31, tzinfo=timezone.utc))),
        _msg(day_marker_content(datetime(2026, 5, 30, tzinfo=timezone.utc))),
    ]
    body = format_previous_week_body(markers)
    assert body.startswith(hc_constants.PREVIOUS_WEEK_PIN_PREFIX)
    assert "https://example/jump" in body
    assert "May 31, 2026" in body


if __name__ == "__main__":
    test_day_marker_content()
    test_is_and_parse_marker()
    test_previous_week_body()
    print("ok")
