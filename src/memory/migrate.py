"""One-time migration from legacy user_memory to 3-layer memory + snapshots."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.memory.database import (
    get_latest_snapshot,
    load_memory,
    load_profile,
    save_preference,
    save_profile,
    save_snapshot,
    list_legacy_user_ids_without_profile,
)
from src.memory.models import (
    AnalysisSnapshot,
    PreferenceSource,
    UserPreference,
    UserProfile,
)

logger = logging.getLogger(__name__)


def _legacy_to_target_direction(last_plan_target: str) -> str:
    if not last_plan_target.strip():
        return ""
    return last_plan_target.replace(" - ", "·").replace("-", "·").strip()


def _build_snapshot_from_legacy(user_id: str, legacy) -> AnalysisSnapshot | None:
    if not (legacy.last_plan_target or legacy.last_matched_industries or legacy.last_profile_summary):
        return None
    now = datetime.now(timezone.utc).isoformat()
    target = _legacy_to_target_direction(legacy.last_plan_target)
    narrative_parts = []
    if target:
        narrative_parts.append(f"目标 {target}")
    if legacy.last_matched_industries:
        narrative_parts.append(f"匹配：{'/'.join(legacy.last_matched_industries[:3])}")
    if legacy.last_profile_summary:
        narrative_parts.append(f"优势：{legacy.last_profile_summary[:60]}")
    narrative = "。".join(narrative_parts)[:200]

    return AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        user_id=user_id,
        analysis_id=f"legacy-{user_id}",
        created_at=legacy.updated_at or now,
        target_direction=target,
        top_industries=legacy.last_matched_industries[:3],
        top_roles=[],
        strength_summary=legacy.last_profile_summary[:120],
        gap_summary=", ".join(legacy.recurring_gaps[:3])[:120],
        plan_milestone="",
        user_constraints=legacy.constraints[:80],
        narrative=narrative or "从旧版记忆迁移",
    )


async def migrate_legacy_user(user_id: str) -> bool:
    """Migrate one user from user_memory if no profile exists. Returns True if migrated."""
    if await load_profile(user_id):
        return False

    legacy = await load_memory(user_id)
    if not legacy:
        return False

    strengths: list[str] = []
    if legacy.last_profile_summary:
        strengths.append(legacy.last_profile_summary[:80])

    profile = UserProfile(
        user_id=user_id,
        target_direction=_legacy_to_target_direction(legacy.last_plan_target),
        recurring_gaps=list(legacy.recurring_gaps),
        core_strengths=strengths,
        interview_count=legacy.interview_count,
        avg_readiness_score=legacy.avg_readiness_score,
        transition_stage="decided" if legacy.last_plan_target else "exploring",
        analysis_count=1 if legacy.last_profile_summary else 0,
    )
    await save_profile(profile)

    for direction in legacy.preferred_directions:
        if not direction.strip():
            continue
        await save_preference(UserPreference(
            user_id=user_id,
            key="industry",
            value=direction.strip(),
            source=PreferenceSource.EXPLICIT,
            confidence=1.0,
        ))

    if not await get_latest_snapshot(user_id):
        snapshot = _build_snapshot_from_legacy(user_id, legacy)
        if snapshot:
            await save_snapshot(snapshot)

    logger.info("Migrated legacy memory for user %s", user_id)
    return True


async def migrate_legacy_if_needed(user_id: str) -> bool:
    """Lazy migration hook — safe to call on every memory read."""
    return await migrate_legacy_user(user_id)


async def migrate_all_legacy() -> int:
    """Migrate all users still on legacy user_memory only. Returns count migrated."""
    user_ids = await list_legacy_user_ids_without_profile()
    count = 0
    for user_id in user_ids:
        if await migrate_legacy_user(user_id):
            count += 1
    logger.info("Legacy migration complete: %d users", count)
    return count
