"""Per-set submission / veto policy keyed by Discord channel and set id."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import hc_constants
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


HC91_SUBMISSIONS = SetConfig(
    set_id=hc_constants.ACTIVE_CUBE_ID,
    submission_channel=hc_constants.SUBMISSIONS_CHANNEL,
    card_list_channel=hc_constants.NINE_CARD_LIST,
    threshold=hc_constants.SUBMISSIONS_THRESHOLD,
    cooldown_hours=float(hc_constants.SUBMISSION_COOLDOWN),
    cooldown_mode="scubusiness",
    state_file=hc_constants.SUBMISSIONS_STATE_FILE,
    closed_on_tue_sat=True,
)

PL1_CARD_PILE = SetConfig(
    set_id=hc_constants.PL1,
    submission_channel=hc_constants.CARD_PILE_1_CHANNEL,
    card_list_channel=None,
    threshold=hc_constants.CARD_PILE_THRESHOLD,
    cooldown_hours=float(hc_constants.CARD_PILE_COOLDOWN),
    cooldown_mode="wall",
    state_file=hc_constants.CARD_PILE_STATE_FILE,
    vc_mention_user_ids=hc_constants.CARD_PILE_VC_USERS,
    veto_content_prefix="PL1: ",
    closed_on_tue_sat=False,
)

SET_CONFIGS: tuple[SetConfig, ...] = (HC91_SUBMISSIONS, PL1_CARD_PILE)

_CONFIG_BY_CHANNEL: dict[int, SetConfig] = {
    cfg.submission_channel: cfg
    for cfg in SET_CONFIGS
    if cfg.submission_channel is not None
}

_CONFIG_BY_SET_ID: dict[str, SetConfig] = {
    cfg.set_id.strip().lower().replace("_", "."): cfg for cfg in SET_CONFIGS
}


def config_for_submission_channel(channel_id: int) -> SetConfig | None:
    return _CONFIG_BY_CHANNEL.get(channel_id)


def config_for_set_id(set_id: str) -> SetConfig | None:
    return _CONFIG_BY_SET_ID.get(set_id.strip().lower().replace("_", "."))


def submission_check_configs() -> tuple[SetConfig, ...]:
    """Sets that use the shared community-poll → veto-polls background checker."""
    return SET_CONFIGS


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


def set_id_from_veto_poll_content(content: str) -> str | None:
    """Return configured set id when veto-polls content carries a known prefix."""
    text = (content or "").strip()
    for cfg in SET_CONFIGS:
        prefix = cfg.veto_content_prefix
        if not prefix:
            continue
        if text.startswith(prefix.strip()):
            return cfg.set_id
    if text.startswith(f"{hc_constants.CUBE_NAME}:"):
        return hc_constants.ACTIVE_CUBE_ID
    return None


def strip_veto_set_prefix(content: str) -> str:
    """First line content without set prefix (for parsing card name / author)."""
    text = (content or "").strip()
    for cfg in SET_CONFIGS:
        prefix = cfg.veto_content_prefix
        if prefix and text.startswith(prefix.strip()):
            return text[len(prefix.strip()) :].lstrip()
    cube_prefix = f"{hc_constants.CUBE_NAME}:"
    if text.startswith(cube_prefix):
        return text[len(cube_prefix) :].lstrip()
    return text


def compile_targets_for_veto_content(content: str) -> tuple[str, int]:
    """Resolve database set id and card-list channel for compile-veto acceptance."""
    detected = set_id_from_veto_poll_content(content)
    if detected:
        return detected, card_list_channel_for_set_config(detected)
    return hc_constants.ACTIVE_CUBE_ID, hc_constants.NINE_CARD_LIST


def card_list_channel_for_set_config(set_id: str) -> int:
    cfg = config_for_set_id(set_id)
    if cfg and cfg.card_list_channel is not None:
        return cfg.card_list_channel
    return hc_constants.HKL_CARD_LIST
