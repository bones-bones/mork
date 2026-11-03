"""SetConfig type and pure helpers for submission / veto policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from cogs.lifecycle.submissions_closed import elapsed_open_hours

CooldownMode = Literal["scubusiness", "wall"]


@dataclass(frozen=True)
class SetConfig:
    set_id: str
    submission_channel: int | None
    card_list_channel: int | None
    threshold: int | None
    cooldown_hours: float | None
    cooldown_mode: CooldownMode = "wall"
    state_file: str | None = None
    vc_mention_user_ids: tuple[int, ...] = ()
    veto_content_prefix: str | None = None
    closed_on_tue_sat: bool = False


def hours_since_last_submission(last: datetime, config: SetConfig) -> float:
    if config.cooldown_mode == "scubusiness":
        return elapsed_open_hours(last)
    return (datetime.now(tz=UTC) - last.astimezone(UTC)).total_seconds() / 3600


def cooldown_wait_message(config: SetConfig, hours_elapsed: float) -> str:
    need = config.cooldown_hours or 0
    if config.cooldown_mode == "scubusiness":
        return (
            f"You've submitted a card within the past {hours_elapsed:.1f} scubusiness hours. "
            f"You need to wait {need} scubusiness hours between submitting cards. "
            f"(Scubusiness hours exclude Saturday and Tuesday.)"
        )
    return (
        f"You've submitted a card within the past {hours_elapsed:.1f} hours. "
        f"You need to wait {need} wall-clock hours between submitting cards."
    )


def veto_content_for_submission(config: SetConfig, content_no_mentions: str) -> str:
    prefix = config.veto_content_prefix
    if not prefix:
        return content_no_mentions
    stripped = prefix.strip()
    if content_no_mentions.startswith(stripped):
        return content_no_mentions
    return f"{prefix}{content_no_mentions}"
