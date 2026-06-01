"""Integration tests for pipeline memory persistence (no LLM)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from src.memory import database as db
from src.memory.models import (
    EventType,
    MemoryEvent,
    UserMemory,
    UserProfile,
)
from src.memory.migrate import migrate_legacy_user
from src.memory.router import build_agent_memory
from src.memory.snapshot import build_analysis_snapshot
from src.pipeline import PipelineRun, save_pipeline_results
from src.schemas.models import (
    IndustryFit,
    IndustryMatch,
    Phase,
    PipelineResult,
    PolishedResume,
    ResumeSection,
    TalentProfile,
    TransitionPlan,
    UserInput,
)


def _minimal_pipeline_result() -> PipelineResult:
    fit = IndustryFit(
        industry="SaaS",
        role="产品经理",
        fit_score=85,
        rationale="匹配",
        skill_gaps=["B端经验"],
    )
    return PipelineResult(
        talent_profile=TalentProfile(
            summary="沟通与结构化思维强",
            years_of_experience=5,
            current_role="建筑师",
        ),
        industry_match=IndustryMatch(
            top_matches=[fit],
            chosen_target=fit,
        ),
        transition_plan=TransitionPlan(
            chosen_target=fit,
            total_timeline="6个月",
            phases=[
                Phase(
                    phase_number=1,
                    title="入门",
                    duration="1个月",
                    objectives=["了解行业"],
                    actions=["读报告"],
                    milestone="完成3份竞品分析",
                ),
            ],
        ),
        polished_resume=PolishedResume(
            target_role="产品经理",
            target_industry="SaaS",
            sections=[
                ResumeSection(
                    section="简介",
                    original="原",
                    polished="新",
                    changes_made=["强化叙事"],
                ),
            ],
            overall_narrative="从空间思维到产品思维",
        ),
    )


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "pipeline_memory.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    asyncio.run(db.init_db())
    return db_path


@pytest.mark.asyncio
async def test_save_pipeline_writes_snapshot_not_legacy(temp_db, monkeypatch):
    user_id = "pipeline-user-1"
    user_input = UserInput(
        user_id=user_id,
        resume_text="5年建筑设计经验",
        background="想转产品",
        constraints="上海",
        target_direction="SaaS产品",
    )

    legacy_before = UserMemory(
        user_id=user_id,
        last_profile_summary="旧摘要",
        last_plan_target="旧行业 - 旧岗位",
    )
    await db.save_memory(legacy_before)
    legacy_frozen = await db.load_memory(user_id)
    assert legacy_frozen is not None
    frozen_updated_at = legacy_frozen.updated_at

    async def fake_extract(*_args, **_kwargs):
        profile = UserProfile(user_id=user_id, city="上海", target_direction="SaaS·产品经理")
        await db.save_profile(profile)
        event = MemoryEvent(
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=EventType.ANALYSIS,
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary="测试分析",
        )
        await db.add_event(event)
        return profile, event

    monkeypatch.setattr("src.pipeline.extract_and_update_memory", fake_extract)

    run = PipelineRun(result=_minimal_pipeline_result())
    await save_pipeline_results(user_input, run)

    legacy_after = await db.load_memory(user_id)
    assert legacy_after is not None
    assert legacy_after.last_profile_summary == "旧摘要"
    assert legacy_after.updated_at == frozen_updated_at

    snapshot = await db.get_latest_snapshot(user_id)
    assert snapshot is not None
    assert snapshot.top_industries == ["SaaS"]
    assert "产品经理" in snapshot.target_direction

    profile = await db.load_profile(user_id)
    assert profile is not None
    assert profile.last_analysis_id == snapshot.analysis_id


@pytest.mark.asyncio
async def test_legacy_migration_populates_profile_and_snapshot(temp_db):
    user_id = "legacy-user-1"
    await db.save_memory(UserMemory(
        user_id=user_id,
        last_profile_summary="空间设计能力强",
        last_matched_industries=["UX", "产品"],
        last_plan_target="科技 - UX设计师",
        preferred_directions=["UX", "交互"],
        recurring_gaps=["行业术语"],
        interview_count=2,
        avg_readiness_score=72.0,
        updated_at="2025-06-01T00:00:00+00:00",
    ))

    migrated = await migrate_legacy_user(user_id)
    assert migrated is True

    profile = await db.load_profile(user_id)
    assert profile is not None
    assert profile.target_direction == "科技·UX设计师"
    assert profile.interview_count == 2

    snapshot = await db.get_latest_snapshot(user_id)
    assert snapshot is not None
    assert "UX" in snapshot.top_industries

    text = await build_agent_memory("market_matcher", user_id)
    assert "UX设计师" in text or "科技" in text


@pytest.mark.asyncio
async def test_per_agent_memory_slices_differ(temp_db):
    user_id = "slice-user-1"
    await db.save_profile(UserProfile(
        user_id=user_id,
        city="深圳",
        target_direction="AI·产品经理",
        transition_stage="decided",
        core_strengths=["逻辑"],
        recurring_gaps=["ML基础"],
    ))
    await db.save_snapshot(
        build_analysis_snapshot(
            user_id,
            "a1",
            UserInput(user_id=user_id, resume_text="x"),
            _minimal_pipeline_result(),
        )
    )

    p1 = await build_agent_memory("profile_analyzer", user_id)
    p2 = await build_agent_memory("market_matcher", user_id)
    assert "深圳" in p1
    assert "缺口" in p2 or "SaaS" in p2
    assert p1 != p2
