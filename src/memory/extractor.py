"""
Memory Extractor — runs after each pipeline to extract durable facts.

Uses a lightweight LLM call (Haiku) to:
1. Extract/update structured profile fields from pipeline results
2. Generate a timeline event summarizing what happened
3. Infer user preferences from patterns
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.llm.client import LLMClient
from src.memory.models import (
    UserProfile, MemoryEvent, UserPreference,
    EventType, PreferenceSource,
)
from src.memory.database import (
    load_profile, save_profile,
    add_event, load_preferences, save_preference,
)

logger = logging.getLogger(__name__)

# Use Haiku for extraction — fast + cheap, no need for Opus here
_extractor_llm = LLMClient(model="claude-sonnet-4-20250514")


# ── Extraction schema ────────────────────────────────────────────

class ProfileExtraction(BaseModel):
    """LLM 从 pipeline 结果中提取的用户档案更新。"""
    name: str = ""
    age: int = 0
    gender: str = ""
    city: str = ""
    education: str = ""
    years_of_experience: int = 0
    current_role: str = ""
    current_industry: str = ""
    current_salary_range: str = ""
    family_situation: str = ""
    core_strengths: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    personality_tags: list[str] = Field(default_factory=list)
    recurring_gaps: list[str] = Field(default_factory=list)
    transition_stage: str = ""
    target_direction: str = ""
    confidence_level: str = ""
    event_summary: str = Field(description="一句话概括本次分析的核心发现")
    insights: list[str] = Field(
        default_factory=list,
        description="值得长期记住的洞察（如'用户有很强的空间思维能力，适合UX设计'）",
    )
    inferred_preferences: list[dict] = Field(
        default_factory=list,
        description="推断出的偏好，格式: [{key: 'industry', value: '科技', reason: '...'}]",
    )


EXTRACTION_PROMPT = """你是一个记忆提取器。你的任务是从转行分析的结果中提取值得长期记住的用户信息。

## 规则

1. 只提取有明确证据的信息，不要猜测
2. 如果某个字段在输入中没有提到，留空（字符串留""，数字留0，列表留[]）
3. core_strengths / transferable_skills / personality_tags：提取关键词，不要长句
4. recurring_gaps：只记录反复出现的短板，不是一次性的
5. transition_stage 只能是：exploring / decided / preparing / switching / settled
6. confidence_level 只能是：low / medium / high
7. event_summary：一句话，20字以内
8. insights：只记录有长期价值的洞察，不要流水账
9. inferred_preferences：只记录有明确行为证据的偏好推断

## 已有档案（如果有的话，请在此基础上更新，不要丢失已有信息）

{existing_profile}

## 已有偏好

{existing_preferences}
"""


# ── Public API ───────────────────────────────────────────────────

async def extract_and_update_memory(
    user_id: str,
    user_input_json: str,
    pipeline_result_json: str,
) -> tuple[UserProfile, MemoryEvent]:
    """Run memory extraction after a pipeline completes.

    Returns the updated profile and the new event.
    """
    # Load existing state
    existing_profile = await load_profile(user_id)
    existing_prefs = await load_preferences(user_id)

    profile_str = json.dumps(
        existing_profile.model_dump(), ensure_ascii=False, indent=2
    ) if existing_profile else "无（新用户）"

    prefs_str = json.dumps(
        [{"key": p.key, "value": p.value, "source": p.source} for p in existing_prefs],
        ensure_ascii=False,
    ) if existing_prefs else "无"

    system = EXTRACTION_PROMPT.format(
        existing_profile=profile_str,
        existing_preferences=prefs_str,
    )

    user_msg = (
        f"## 用户输入\n{user_input_json}\n\n"
        f"## Pipeline 分析结果\n{pipeline_result_json}"
    )

    try:
        extraction = await _extractor_llm.generate(system, user_msg, ProfileExtraction)
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")
        # Return existing profile unchanged + a minimal event
        profile = existing_profile or UserProfile(user_id=user_id)
        event = MemoryEvent(
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=EventType.ANALYSIS,
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary="分析完成（记忆提取失败）",
        )
        await add_event(event)
        return profile, event

    # ── Merge extraction into profile ────────────────────────────
    profile = existing_profile or UserProfile(user_id=user_id)
    profile = _merge_profile(profile, extraction)
    profile.analysis_count += 1
    await save_profile(profile)

    # ── Create timeline event ────────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()
    event = MemoryEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        event_type=EventType.ANALYSIS,
        timestamp=now,
        summary=extraction.event_summary or "完成一次转行分析",
        details=json.dumps({
            "target_direction": extraction.target_direction,
            "confidence_level": extraction.confidence_level,
        }, ensure_ascii=False),
        insights=extraction.insights,
    )
    await add_event(event)

    # ── Save inferred preferences ────────────────────────────────
    for pref_dict in extraction.inferred_preferences:
        if pref_dict.get("key") and pref_dict.get("value"):
            pref = UserPreference(
                user_id=user_id,
                key=pref_dict["key"],
                value=pref_dict["value"],
                source=PreferenceSource.INFERRED,
                confidence=0.7,
                created_at=now,
            )
            await save_preference(pref)

    logger.info(
        f"Memory updated for {user_id}: "
        f"profile={profile.name or 'unnamed'}, "
        f"event={event.summary}, "
        f"prefs={len(extraction.inferred_preferences)} inferred"
    )
    return profile, event


async def extract_interview_memory(
    user_id: str,
    interview_report_json: str,
) -> MemoryEvent:
    """Extract memory from a completed interview session."""
    profile = await load_profile(user_id)
    if profile:
        profile.interview_count += 1
        # Update avg readiness from report if available
        try:
            report = json.loads(interview_report_json)
            score = report.get("overall_readiness", 0)
            if score > 0:
                # Running average
                n = profile.interview_count
                profile.avg_readiness_score = (
                    (profile.avg_readiness_score * (n - 1) + score) / n
                )
        except (json.JSONDecodeError, TypeError):
            pass
        await save_profile(profile)

    now = datetime.now(timezone.utc).isoformat()
    event = MemoryEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        event_type=EventType.INTERVIEW,
        timestamp=now,
        summary=f"完成第 {profile.interview_count if profile else 1} 次模拟面试",
        details=interview_report_json[:2000],  # Truncate if huge
        insights=[],  # Could add LLM extraction here too
    )
    await add_event(event)
    return event


# ── Internal: merge logic ────────────────────────────────────────

def _merge_profile(existing: UserProfile, extraction: ProfileExtraction) -> UserProfile:
    """Merge extracted fields into existing profile. Non-empty extraction wins."""
    # Simple fields: extraction overwrites if non-empty
    for field in (
        "name", "gender", "city", "education", "current_role",
        "current_industry", "current_salary_range", "family_situation",
        "target_direction",
    ):
        new_val = getattr(extraction, field)
        if new_val:
            setattr(existing, field, new_val)

    # Numeric fields: extraction overwrites if > 0
    for field in ("age", "years_of_experience"):
        new_val = getattr(extraction, field)
        if new_val > 0:
            setattr(existing, field, new_val)

    # Enum-like fields
    if extraction.transition_stage in ("exploring", "decided", "preparing", "switching", "settled"):
        existing.transition_stage = extraction.transition_stage
    if extraction.confidence_level in ("low", "medium", "high"):
        existing.confidence_level = extraction.confidence_level

    # List fields: union (deduplicate)
    for field in ("core_strengths", "transferable_skills", "personality_tags", "recurring_gaps"):
        old_set = set(getattr(existing, field))
        new_items = getattr(extraction, field)
        merged = list(old_set | set(new_items))
        setattr(existing, field, merged)

    return existing
