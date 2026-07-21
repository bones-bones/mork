"""Smoke tests for submissions day marker helpers (no Discord)."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import hc_constants  # noqa: E402
from cogs.lifecycle.submissions_day_markers import (  # noqa: E402
    day_marker_content,
    day_marker_iso_date,
    format_previous_week_body,
    has_image_attachment,
    is_submissions_card,
    is_submissions_day_marker,
    submission_period_start,
    utc_day_start,
)


def _msg(content: str, author_id: int = hc_constants.MORK_2, attachments=None):
    return SimpleNamespace(
        content=content,
        author=SimpleNamespace(id=author_id),
        jump_url="https://example/jump",
        attachments=attachments or [],
    )


def _attachment(filename="card.png", content_type="image/png"):
    return SimpleNamespace(filename=filename, content_type=content_type)


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


def test_is_submissions_card():
    card = _msg("Cool Card by @user", author_id=hc_constants.MORK_2, attachments=[_attachment()])
    assert is_submissions_card(card)
    assert not is_submissions_card(_msg(day_marker_content(datetime(2026, 6, 1, tzinfo=timezone.utc))))
    assert not is_submissions_card(_msg("no attachment", author_id=hc_constants.MORK_2))
    assert not is_submissions_card(
        _msg("reminder", author_id=hc_constants.MORK_2, attachments=[_attachment("notes.txt", "text/plain")])
    )
    assert not is_submissions_card(_msg("user card", author_id=123, attachments=[_attachment()]))


def test_has_image_attachment():
    assert has_image_attachment(_msg("card", attachments=[_attachment()]))
    assert has_image_attachment(_msg("card", attachments=[_attachment("card.jpg", None)]))
    assert not has_image_attachment(_msg("text only"))
    assert not has_image_attachment(_msg("file", attachments=[_attachment("doc.pdf", "application/pdf")]))


def test_submission_period_start():
    now = datetime(2026, 6, 3, 1, 0, tzinfo=timezone.utc)
    marker = _msg(day_marker_content(datetime(2026, 6, 1, 1, 0, tzinfo=timezone.utc)))
    marker.created_at = datetime(2026, 6, 1, 1, 0, tzinfo=timezone.utc)
    assert submission_period_start(now, None) == utc_day_start(now) - timedelta(days=1)
    assert submission_period_start(now, marker) == datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)


def test_is_submissions_day_marker_any_mork_account():
    day = datetime(2026, 6, 1, tzinfo=timezone.utc)
    for author_id in (hc_constants.MORK, hc_constants.MORK_2, hc_constants.MORK_3):
        assert is_submissions_day_marker(_msg(day_marker_content(day), author_id=author_id))


if __name__ == "__main__":
    test_day_marker_content()
    test_is_and_parse_marker()
    test_previous_week_body()
    test_is_submissions_card()
    test_has_image_attachment()
    test_submission_period_start()
    test_is_submissions_day_marker_any_mork_account()
    print("ok")
