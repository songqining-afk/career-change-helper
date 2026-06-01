"""Format memory slices into prompt-ready text with hard char limits."""

from __future__ import annotations

from src.memory.models import MemoryEvent, UserPreference, UserProfile, AnalysisSnapshot
from src.memory.slices import AgentMemorySliceConfig

PROFILE_LABELS: dict[str, str] = {
    "name": "姓名",
    "city": "城市",
    "education": "学历",
    "years_of_experience": "工作年限",
    "current_role": "当前职位",
    "current_industry": "当前行业",
    "family_situation": "家庭状况",
    "core_strengths": "核心优势",
    "transferable_skills": "可迁移能力",
    "personality_tags": "性格标签",
    "recurring_gaps": "反复短板",
    "target_direction": "目标方向",
    "previous_target_direction": "曾目标方向",
    "transition_stage": "转行阶段",
    "confidence_level": "信心程度",
    "current_salary_range": "薪资范围",
    "interview_count": "模拟面试次数",
    "avg_readiness_score": "平均准备度",
}


def _trim_list(items: list[str], max_items: int) -> list[str]:
    return items[:max_items] if max_items > 0 else items


def _format_profile_field(
    profile: UserProfile,
    field: str,
    max_list_items: int,
) -> str | None:
    label = PROFILE_LABELS.get(field, field)
    val = getattr(profile, field, None)
    if val is None:
        return None
    if isinstance(val, list):
        items = _trim_list([x for x in val if x], max_list_items)
        if not items:
            return None
        return f"{label}: {', '.join(items)}"
    if isinstance(val, int):
        if field == "years_of_experience" and val <= 0:
            return None
        if field == "interview_count" and val <= 0:
            return None
        if field == "interview_count":
            score = profile.avg_readiness_score
            if score > 0:
                return f"{label}: {val} 次，平均准备度 {score:.0f}/100"
            return f"{label}: {val} 次"
        if val <= 0:
            return None
        suffix = "年" if field == "years_of_experience" else ""
        return f"{label}: {val}{suffix}"
    if isinstance(val, float):
        if val <= 0:
            return None
        return f"{label}: {val:.0f}"
    if not str(val).strip():
        return None
    return f"{label}: {val}"


def format_memory_slice(
    cfg: AgentMemorySliceConfig,
    profile: UserProfile | None,
    snapshot: AnalysisSnapshot | None,
    preferences: list[UserPreference],
    events: list[MemoryEvent],
) -> str:
    parts: list[str] = []

    if profile and cfg.profile_fields:
        lines: list[str] = []
        fields = list(cfg.profile_fields)
        if cfg.include_target_if_not_exploring:
            if profile.transition_stage != "exploring" and profile.target_direction:
                if "target_direction" not in fields:
                    fields.append("target_direction")
        for f in fields:
            line = _format_profile_field(profile, f, cfg.list_field_max_items)
            if line:
                lines.append(line)
        if lines:
            parts.append("【已知档案】\n" + "\n".join(lines))

    if snapshot and cfg.snapshot_fields:
        snap_lines: list[str] = []
        for f in cfg.snapshot_fields:
            if f == "narrative":
                text = snapshot.narrative
                if cfg.snapshot_narrative_max_chars > 0:
                    text = text[: cfg.snapshot_narrative_max_chars]
                if text:
                    snap_lines.append(text)
                continue
            val = getattr(snapshot, f, None)
            if isinstance(val, list):
                if val:
                    label = {"top_industries": "上次匹配行业", "top_roles": "上次匹配岗位"}.get(f, f)
                    snap_lines.append(f"{label}: {', '.join(val[:3])}")
            elif val and str(val).strip():
                label = {
                    "gap_summary": "缺口",
                    "strength_summary": "优势",
                    "plan_milestone": "阶段建议",
                    "target_direction": "上次目标",
                }.get(f, f)
                snap_lines.append(f"{label}: {val}")
        if snap_lines:
            parts.append("【上次分析摘要】\n" + "\n".join(snap_lines))

    if preferences:
        pref_lines = []
        for p in preferences:
            tag = "明确" if p.source == "explicit" or getattr(p.source, "value", p.source) == "explicit" else "推断"
            pref_lines.append(f"- [{tag}] {p.key}: {p.value}")
        parts.append("【用户偏好】\n" + "\n".join(pref_lines))

    if events:
        event_lines = []
        for e in events[: cfg.event_limit or len(events)]:
            line = f"- [{e.timestamp[:10]}] {e.summary}"
            if e.insights:
                line += f" → {'; '.join(e.insights[:1])}"
            event_lines.append(line)
        parts.append("【相关时间线】\n" + "\n".join(event_lines))

    text = "\n\n".join(parts)
    if len(text) > cfg.max_chars:
        text = text[: cfg.max_chars - 1] + "…"
    return text
