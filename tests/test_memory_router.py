"""Unit tests for per-agent memory slicing and formatting."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.memory import database as db
from src.memory.formatter import format_memory_slice
from src.memory.models import (
    AnalysisSnapshot,
    MemoryEvent,
    UserPreference,
    UserProfile,
    PreferenceSource,
)
from src.memory.router import build_agent_memory
from src.memory.slices import AGENT_MEMORY_SLICES


def test_profile_analyzer_excludes_target_while_exploring():
    cfg = AGENT_MEMORY_SLICES["profile_analyzer"]
    profile = UserProfile(
        user_id="u1",
        city="上海",
        target_direction="UX设计",
        transition_stage="exploring",
        core_strengths=["空间思维"],
    )
    text = format_memory_slice(cfg, profile, None, [], [])
    assert "上海" in text
    assert "空间思维" in text
    assert "目标方向" not in text


def test_market_matcher_includes_snapshot_and_prefs():
    cfg = AGENT_MEMORY_SLICES["market_matcher"]
    profile = UserProfile(
        user_id="u1",
        target_direction="科技·产品经理",
        transition_stage="decided",
        recurring_gaps=["行业术语"],
    )
    snapshot = AnalysisSnapshot(
        snapshot_id="s1",
        user_id="u1",
        analysis_id="a1",
        created_at="2026-01-01T00:00:00+00:00",
        top_industries=["SaaS", "AI"],
        top_roles=["产品经理"],
        gap_summary="缺少B端经验",
        narrative="[2026-01-01] 目标 SaaS·产品经理。匹配：SaaS/AI。优势：沟通强。",
    )
    prefs = [
        UserPreference(user_id="u1", key="industry", value="科技", source="explicit", confidence=1.0),
    ]
    events = [
        MemoryEvent(
            event_id="e1",
            user_id="u1",
            event_type="analysis",
            timestamp="2026-01-01T00:00:00+00:00",
            summary="完成分析",
        ),
    ]
    text = format_memory_slice(cfg, profile, snapshot, prefs, events)
    assert "目标方向" in text
    assert "SaaS" in text
    assert "科技" in text
    assert "完成分析" in text
    assert len(text) <= cfg.max_chars


def test_char_limit_truncation():
    cfg = AGENT_MEMORY_SLICES["cv_optimizer"]
    profile = UserProfile(
        user_id="u1",
        target_direction="X" * 200,
        core_strengths=[f"skill-{i}" for i in range(20)],
        transferable_skills=[f"t-{i}" for i in range(20)],
        recurring_gaps=[f"gap-{i}" for i in range(20)],
    )
    text = format_memory_slice(cfg, profile, None, [], [])
    assert len(text) <= cfg.max_chars


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    asyncio.run(db.init_db())
    return db_path


def test_router_filters_low_confidence_preferences(temp_db):
    async def _run():
        await db.save_preference(UserPreference(
            user_id="u2",
            key="role",
            value="低置信岗位",
            source=PreferenceSource.INFERRED,
            confidence=0.5,
        ))
        await db.save_preference(UserPreference(
            user_id="u2",
            key="industry",
            value="明确行业",
            source=PreferenceSource.EXPLICIT,
            confidence=1.0,
        ))
        text = await build_agent_memory("market_matcher", "u2")
        assert "明确行业" in text
        assert "低置信岗位" not in text

    asyncio.run(_run())
