"""SetConfig type and pure helpers for submission / veto policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cogs.lifecycle.submissions_closed import elapsed_open_hours


@dataclass(frozen=True)
class SetConfig:
    set_id: str
    card_list_channel: int | None
    threshold: int | None
    cooldown_hours: float | None
    vc_mention_user_ids: tuple[int, ...] = ()


def hours_since_last_submission(last: datetime, _config: SetConfig) -> float:
    return elapsed_open_hours(last)


def cooldown_wait_message(config: SetConfig, hours_elapsed: float) -> str:
    need = config.cooldown_hours or 0
    return (
        f"You've submitted a card within the past {hours_elapsed:.1f} scubusiness hours. "
        f"You need to wait {need} scubusiness hours between submitting cards. "
        f"(Scubusiness hours exclude Saturday and Tuesday.)"
    )
