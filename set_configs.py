"""Concrete SetConfig instances for active submission sets."""

from __future__ import annotations

import hc_constants
from set_config import SetConfig

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
    return hc_constants.ACTIVE_CUBE_ID, hc_constants.NINE_CARD_LIST
