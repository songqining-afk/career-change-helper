"""Build compressed analysis snapshots from pipeline results."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.memory.models import AnalysisSnapshot
from src.schemas.models import PipelineResult, UserInput


def build_analysis_snapshot(
    user_id: str,
    analysis_id: str,
    user_input: UserInput,
    result: PipelineResult,
) -> AnalysisSnapshot:
    """Derive a short cross-session summary from a completed pipeline."""
    profile = result.talent_profile
    industry = result.industry_match
    plan = result.transition_plan

    target = plan.chosen_target
    top_industries = [m.industry for m in industry.top_matches[:3]]
    top_roles = [m.role for m in industry.top_matches[:3]]

    gap_parts: list[str] = []
    for m in industry.top_matches[:2]:
        if m.skill_gaps:
            gap_parts.extend(m.skill_gaps[:2])
    gap_summary = "、".join(dict.fromkeys(gap_parts))[:120]

    plan_milestone = ""
    if plan.phases:
        plan_milestone = plan.phases[0].milestone or plan.phases[0].title

    constraints = user_input.constraints or user_input.background
    if len(constraints) > 80:
        constraints = constraints[:77] + "..."

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    narrative = (
        f"[{date_str}] 目标 {target.industry}·{target.role}。"
        f"匹配：{'/'.join(top_industries[:3]) or '—'}。"
        f"优势：{profile.summary[:60]}。"
    )
    if gap_summary:
        narrative += f"缺口：{gap_summary[:40]}。"
    if plan_milestone:
        narrative += f"阶段：{plan_milestone[:40]}。"
    narrative = narrative[:200]

    return AnalysisSnapshot(
        snapshot_id=str(uuid.uuid4()),
        user_id=user_id,
        analysis_id=analysis_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        target_direction=f"{target.industry}·{target.role}",
        top_industries=top_industries,
        top_roles=top_roles,
        strength_summary=profile.summary[:120],
        gap_summary=gap_summary,
        plan_milestone=plan_milestone[:120],
        user_constraints=constraints,
        narrative=narrative,
    )
