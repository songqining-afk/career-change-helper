"""Per-agent memory field whitelists — only inject what each agent needs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentMemorySliceConfig:
    profile_fields: tuple[str, ...] = ()
    snapshot_fields: tuple[str, ...] = ()
    snapshot_narrative_max_chars: int = 0
    preference_keys: tuple[str, ...] = ()
    preference_min_confidence: float = 0.6
    event_types: tuple[str, ...] = ()
    event_limit: int = 0
    list_field_max_items: int = 5
    max_chars: int = 400
    include_target_if_not_exploring: bool = False


AGENT_MEMORY_SLICES: dict[str, AgentMemorySliceConfig] = {
    "profile_analyzer": AgentMemorySliceConfig(
        profile_fields=(
            "city", "education", "years_of_experience", "current_role",
            "current_industry", "family_situation", "core_strengths",
            "transferable_skills", "personality_tags",
        ),
        include_target_if_not_exploring=True,
        max_chars=300,
    ),
    "market_matcher": AgentMemorySliceConfig(
        profile_fields=(
            "target_direction", "previous_target_direction", "transition_stage",
            "recurring_gaps", "current_salary_range",
        ),
        snapshot_fields=("top_industries", "top_roles", "gap_summary", "narrative"),
        snapshot_narrative_max_chars=80,
        preference_keys=(
            "industry", "role", "rejection_industry", "rejection_role",
            "location", "salary",
        ),
        event_types=("direction", "analysis"),
        event_limit=3,
        max_chars=400,
    ),
    "strategy_architect": AgentMemorySliceConfig(
        profile_fields=(
            "target_direction", "previous_target_direction", "transition_stage",
            "confidence_level", "recurring_gaps",
        ),
        snapshot_fields=("plan_milestone", "gap_summary", "target_direction"),
        preference_keys=("location", "salary", "workstyle", "rejection_role"),
        event_types=("direction", "milestone", "analysis"),
        event_limit=3,
        max_chars=350,
    ),
    "cv_optimizer": AgentMemorySliceConfig(
        profile_fields=(
            "target_direction", "core_strengths", "transferable_skills", "recurring_gaps",
        ),
        snapshot_fields=("top_roles", "gap_summary", "strength_summary"),
        preference_keys=("role",),
        list_field_max_items=5,
        max_chars=300,
    ),
    "interview_simulator": AgentMemorySliceConfig(
        profile_fields=(
            "target_direction", "recurring_gaps", "interview_count", "avg_readiness_score",
        ),
        snapshot_fields=("top_roles", "gap_summary"),
        preference_keys=("rejection_role", "rejection_industry"),
        event_types=("interview",),
        event_limit=3,
        max_chars=350,
    ),
}
