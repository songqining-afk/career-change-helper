"""Load and slice SQLite memory per agent — no full-dump into prompts."""

from __future__ import annotations

import logging

from src.memory.migrate import migrate_legacy_if_needed
from src.memory.database import (
    load_profile,
    load_preferences_filtered,
    get_latest_snapshot,
    list_events_by_types,
    load_memory,
)
from src.memory.formatter import format_memory_slice
from src.memory.slices import AGENT_MEMORY_SLICES, AgentMemorySliceConfig

logger = logging.getLogger(__name__)


def _legacy_fallback_text(user_id: str, legacy) -> str:
    parts = []
    if legacy.last_profile_summary:
        parts.append(f"上次竞争力: {legacy.last_profile_summary[:80]}")
    if legacy.last_matched_industries:
        parts.append(f"上次匹配: {', '.join(legacy.last_matched_industries[:3])}")
    if legacy.last_plan_target:
        parts.append(f"上次目标: {legacy.last_plan_target[:60]}")
    if legacy.preferred_directions:
        parts.append(f"偏好方向: {', '.join(legacy.preferred_directions[-3:])}")
    if not parts:
        return ""
    return "【历史记忆（旧版）】\n" + "\n".join(parts)


async def build_agent_memory(agent_key: str, user_id: str) -> str:
    """Return formatted memory text scoped to one agent."""
    await migrate_legacy_if_needed(user_id)

    cfg: AgentMemorySliceConfig | None = AGENT_MEMORY_SLICES.get(agent_key)
    if not cfg:
        logger.warning("Unknown agent memory key: %s", agent_key)
        return ""

    profile = await load_profile(user_id)
    snapshot = await get_latest_snapshot(user_id) if cfg.snapshot_fields else None

    preferences = []
    if cfg.preference_keys:
        preferences = await load_preferences_filtered(
            user_id,
            keys=list(cfg.preference_keys),
            min_confidence=cfg.preference_min_confidence,
        )

    events = []
    if cfg.event_types and cfg.event_limit > 0:
        events = await list_events_by_types(
            user_id,
            event_types=list(cfg.event_types),
            limit=cfg.event_limit,
        )

    text = format_memory_slice(cfg, profile, snapshot, preferences, events)
    if text:
        return text

    legacy = await load_memory(user_id)
    if legacy:
        return _legacy_fallback_text(user_id, legacy)[: cfg.max_chars]

    return ""
