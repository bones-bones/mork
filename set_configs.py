"""Concrete SetConfig instances for active submission sets."""

from __future__ import annotations

from datetime import UTC, datetime

import hc_constants
from cogs.lifecycle.submissions_closed import elapsed_open_hours
from set_config import SetConfig

HC9_1 = SetConfig(
    set_id=hc_constants.ACTIVE_CUBE_ID,
    card_list_channel=hc_constants.NINE_CARD_LIST,
    threshold=60,
    cooldown_hours=22.0,
)

PL1_CARD_PILE = SetConfig(
    set_id="PL1",
    card_list_channel=hc_constants.PL1_CARD_LIST,
    threshold=30,
    cooldown_hours=4.0,
    vc_mention_user_ids=hc_constants.CARD_PILE_VC_USERS,
)

KNOWN_SET_CONFIGS: tuple[SetConfig, ...] = (HC9_1, PL1_CARD_PILE)

# Only one submission set is open at a time; switch when the community changes intake.
ACTIVE_SUBMISSION_SET_CONFIG = HC9_1

SUBMISSIONS_INTAKE_CHANNEL = hc_constants.SUBMISSIONS_CHANNEL

_CONFIG_BY_SET_ID: dict[str, SetConfig] = {
    cfg.set_id.strip().lower().replace("_", "."): cfg for cfg in KNOWN_SET_CONFIGS
}


def active_submission_set() -> SetConfig:
    return ACTIVE_SUBMISSION_SET_CONFIG


def submission_cooldown_still_active(
    last_submit: datetime, now: datetime | None = None
) -> bool:
    """Ledger retention: keep rows while any known set's cooldown could still apply."""
    now = now or datetime.now(tz=UTC)
    elapsed = elapsed_open_hours(last_submit, now)
    for cfg in KNOWN_SET_CONFIGS:
        if elapsed <= float(cfg.cooldown_hours or 0):
            return True
    return False


def active_set_cooldown_blocks(
    last_submit: datetime, config: SetConfig, now: datetime | None = None
) -> bool:
    """Intake gate for the currently active submission set only."""
    now = now or datetime.now(tz=UTC)
    elapsed = elapsed_open_hours(last_submit, now)
    return elapsed < float(config.cooldown_hours or 0)


def is_submissions_intake_channel(channel_id: int) -> bool:
    return channel_id == SUBMISSIONS_INTAKE_CHANNEL


def config_for_set_id(set_id: str) -> SetConfig | None:
    return _CONFIG_BY_SET_ID.get(set_id.strip().lower().replace("_", "."))


def set_id_from_veto_poll_content(content: str) -> str | None:
    """Legacy cube prefix on veto-polls lines; otherwise compile uses active submission set."""
    text = (content or "").strip()
    if text.startswith(f"{hc_constants.CUBE_NAME}:"):
        return hc_constants.ACTIVE_CUBE_ID
    return None


def strip_veto_set_prefix(content: str) -> str:
    """Strip legacy Hellscube: prefix before parsing card name / author."""
    text = (content or "").strip()
    cube_prefix = f"{hc_constants.CUBE_NAME}:"
    if text.startswith(cube_prefix):
        return text[len(cube_prefix) :].lstrip()
    return text


def card_list_channel_for_set_config(set_id: str) -> int:
    cfg = config_for_set_id(set_id)
    if cfg and cfg.card_list_channel is not None:
        return cfg.card_list_channel
    return hc_constants.VETO_CARD_LIST


def compile_targets_for_veto_content(content: str) -> tuple[str, int]:
    """Resolve database set id and card-list channel for compile-veto acceptance."""
    detected = set_id_from_veto_poll_content(content)
    if detected:
        return detected, card_list_channel_for_set_config(detected)
    active = active_submission_set()
    channel = active.card_list_channel or hc_constants.NINE_CARD_LIST
    return active.set_id, channel
