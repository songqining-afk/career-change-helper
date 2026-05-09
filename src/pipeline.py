"""
Pipeline — orchestrates the 5-agent analysis workflow with 3-layer persistent memory + RAG.

SEQUENTIAL INTERACTIVE MODE (default):
    Agent 1 → user confirms → Agent 2 → user confirms → ... → Agent 5

Each agent receives:
  - Its own inputs (structured data from previous agents)
  - Full memory_context (profile + events + preferences)
  - Accumulated user_feedback from all prior interactions (memory inheritance)

Interview (Agent 5) is the final step — runs as a separate multi-turn session.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Awaitable

from src.agents import ProfileAnalyzer, MarketMatcher, StrategyArchitect, CVOptimizer
from src.schemas.models import (
    UserInput, TalentProfile, IndustryMatch,
    TransitionPlan, PolishedResume, PipelineResult,
)
from src.memory.database import (
    load_memory, save_memory, save_analysis, init_db,
    load_profile, load_preferences, list_events,
)
from src.memory.models import UserMemory, AnalysisRecord, UserProfile
from src.memory.extractor import extract_and_update_memory
from src.knowledge import KnowledgeStore

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    agent: str
    duration_s: float
    success: bool
    error: str = ""


@dataclass
class PipelineRun:
    """Tracks a single pipeline execution."""
    steps: list[StepResult] = field(default_factory=list)
    result: PipelineResult | None = None
    # Keep intermediate results for interview session creation
    profile: TalentProfile | None = None
    industry_match: IndustryMatch | None = None
    transition_plan: TransitionPlan | None = None
    polished_resume: PolishedResume | None = None
    total_duration_s: float = 0.0

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)


# ── Memory context builder ───────────────────────────────────────

def _build_memory_context(
    profile: UserProfile | None,
    preferences: list,
    events: list,
) -> str:
    """Build a rich memory context string from the 3-layer memory system."""
    parts = []

    # Layer 1: 用户档案
    if profile:
        profile_lines = []
        if profile.name:
            profile_lines.append(f"姓名: {profile.name}")
        if profile.age:
            profile_lines.append(f"年龄: {profile.age}")
        if profile.city:
            profile_lines.append(f"城市: {profile.city}")
        if profile.education:
            profile_lines.append(f"学历: {profile.education}")
        if profile.current_role:
            profile_lines.append(f"当前职位: {profile.current_role}")
        if profile.current_industry:
            profile_lines.append(f"当前行业: {profile.current_industry}")
        if profile.years_of_experience:
            profile_lines.append(f"工作年限: {profile.years_of_experience}年")
        if profile.current_salary_range:
            profile_lines.append(f"薪资范围: {profile.current_salary_range}")
        if profile.family_situation:
            profile_lines.append(f"家庭状况: {profile.family_situation}")
        if profile.core_strengths:
            profile_lines.append(f"核心优势: {', '.join(profile.core_strengths)}")
        if profile.transferable_skills:
            profile_lines.append(f"可迁移能力: {', '.join(profile.transferable_skills)}")
        if profile.personality_tags:
            profile_lines.append(f"性格标签: {', '.join(profile.personality_tags)}")
        if profile.recurring_gaps:
            profile_lines.append(f"反复短板: {', '.join(profile.recurring_gaps)}")
        if profile.target_direction:
            profile_lines.append(f"当前目标方向: {profile.target_direction}")
        if profile.transition_stage != "exploring":
            profile_lines.append(f"转行阶段: {profile.transition_stage}")
        if profile.analysis_count:
            profile_lines.append(f"已分析 {profile.analysis_count} 次")
        if profile.interview_count:
            profile_lines.append(
                f"已面试 {profile.interview_count} 次，"
                f"平均准备度 {profile.avg_readiness_score:.0f}/100"
            )
        if profile_lines:
            parts.append("【用户档案】\n" + "\n".join(profile_lines))

    # Layer 2: 最近事件（最多5条）
    if events:
        event_lines = []
        for e in events[:5]:
            line = f"- [{e.timestamp[:10]}] {e.summary}"
            if e.insights:
                line += f" → 洞察: {'; '.join(e.insights[:2])}"
            event_lines.append(line)
        parts.append("【转行时间线】\n" + "\n".join(event_lines))

    # Layer 3: 偏好
    if preferences:
        pref_lines = []
        for p in preferences:
            source_tag = "明确" if p.source == "explicit" else "推断"
            pref_lines.append(f"- [{source_tag}] {p.key}: {p.value}")
        parts.append("【用户偏好】\n" + "\n".join(pref_lines))

    return "\n\n".join(parts) if parts else ""


def _build_legacy_history_context(memory: UserMemory) -> str:
    """Fallback: build context from legacy UserMemory (backward compat)."""
    parts = []
    if memory.last_profile_summary:
        parts.append(f"上次分析的核心竞争力: {memory.last_profile_summary}")
    if memory.last_matched_industries:
        parts.append(f"上次匹配的行业方向: {', '.join(memory.last_matched_industries)}")
    if memory.last_plan_target:
        parts.append(f"上次选定的转行目标: {memory.last_plan_target}")
    if memory.interview_count > 0:
        parts.append(
            f"已完成 {memory.interview_count} 次模拟面试，"
            f"平均准备度 {memory.avg_readiness_score:.0f}/100"
        )
    if memory.recurring_gaps:
        parts.append(f"反复出现的短板: {', '.join(memory.recurring_gaps)}")
    if memory.preferred_directions:
        parts.append(f"用户偏好方向: {', '.join(memory.preferred_directions)}")
    return "\n".join(parts) if parts else ""


def _build_feedback_context(feedback_history: list[dict]) -> str:
    """Build accumulated user feedback into a context string for memory inheritance.

    Each entry: {"agent": "能力画像专家", "feedback": "用户的反馈内容"}
    """
    if not feedback_history:
        return ""
    lines = ["【用户在本次分析中的反馈记录】"]
    for entry in feedback_history:
        lines.append(f"- {entry['agent']}阶段，用户反馈: {entry['feedback']}")
    return "\n".join(lines)


# ── Step-by-step pipeline functions ──────────────────────────────

async def load_pipeline_context(user_input: UserInput) -> tuple[str, str, KnowledgeStore]:
    """Load memory context and initialize knowledge store. Returns (memory_context, legacy_context, kb)."""
    await init_db()
    user_profile = await load_profile(user_input.user_id)
    user_prefs = await load_preferences(user_input.user_id)
    recent_events = await list_events(user_input.user_id, limit=5)
    memory_context = _build_memory_context(user_profile, user_prefs, recent_events)

    legacy_context = ""
    if not memory_context:
        legacy_memory = await load_memory(user_input.user_id)
        if legacy_memory:
            legacy_context = _build_legacy_history_context(legacy_memory)
            memory_context = legacy_context

    kb = KnowledgeStore()
    return memory_context, legacy_context, kb


async def run_step1(
    user_input: UserInput,
    memory_context: str,
    feedback_history: list[dict],
    kb: KnowledgeStore,
) -> TalentProfile:
    """Agent 1: 能力画像专家"""
    feedback_ctx = _build_feedback_context(feedback_history)
    combined_memory = "\n\n".join(filter(None, [memory_context, feedback_ctx]))

    resume_rag = kb.get_rag_context(
        user_input.user_id,
        query=user_input.resume_text[:200],
        top_k=3,
        doc_type="resume",
    )
    analyzer = ProfileAnalyzer()
    return await analyzer.analyze(
        user_input,
        rag_context=resume_rag,
        memory_context=combined_memory,
    )


async def run_step2(
    user_input: UserInput,
    profile: TalentProfile,
    memory_context: str,
    feedback_history: list[dict],
    kb: KnowledgeStore,
    rag_context: str = "",
) -> IndustryMatch:
    """Agent 2: 市场匹配引擎"""
    feedback_ctx = _build_feedback_context(feedback_history)
    combined_memory = "\n\n".join(filter(None, [memory_context, feedback_ctx]))

    market_query = f"{profile.summary} {' '.join(profile.industries_touched)}"
    industry_rag = rag_context or kb.get_rag_context(
        user_input.user_id, query=market_query, top_k=5, doc_type="industry",
    )
    jd_rag = kb.get_rag_context(
        user_input.user_id, query=market_query, top_k=3, doc_type="jd",
    )
    combined_market_rag = "\n\n".join(filter(None, [industry_rag, jd_rag]))

    matcher = MarketMatcher()
    return await matcher.analyze(
        profile,
        rag_context=combined_market_rag,
        memory_context=combined_memory,
    )


async def run_step3(
    user_input: UserInput,
    profile: TalentProfile,
    industry: IndustryMatch,
    memory_context: str,
    feedback_history: list[dict],
    kb: KnowledgeStore,
) -> TransitionPlan:
    """Agent 3: 路径规划架构师"""
    feedback_ctx = _build_feedback_context(feedback_history)
    combined_memory = "\n\n".join(filter(None, [memory_context, feedback_ctx]))

    # Use user's chosen target if available, otherwise fallback to top match
    target = industry.chosen_target or (industry.top_matches[0] if industry.top_matches else None)
    
    market_query = f"{profile.summary} {' '.join(profile.industries_touched)}"
    plan_query = f"{target.industry} {target.role}" if target else market_query
    plan_rag = kb.get_rag_context(
        user_input.user_id, query=plan_query, top_k=5, doc_type="industry",
    )
    plan_jd_rag = kb.get_rag_context(
        user_input.user_id, query=plan_query, top_k=3, doc_type="jd",
    )
    combined_plan_rag = "\n\n".join(filter(None, [plan_rag, plan_jd_rag]))

    architect = StrategyArchitect()
    return await architect.analyze(
        profile, industry,
        rag_context=combined_plan_rag,
        memory_context=combined_memory,
    )


async def run_step4(
    user_input: UserInput,
    profile: TalentProfile,
    plan: TransitionPlan,
    memory_context: str,
    feedback_history: list[dict],
    kb: KnowledgeStore,
) -> PolishedResume:
    """Agent 4: 简历润色助手"""
    feedback_ctx = _build_feedback_context(feedback_history)
    combined_memory = "\n\n".join(filter(None, [memory_context, feedback_ctx]))

    cv_query = f"{plan.chosen_target.industry} {plan.chosen_target.role} 简历"
    template_rag = kb.get_rag_context(
        user_input.user_id, query=cv_query, top_k=3, doc_type="template",
    )
    optimizer = CVOptimizer()
    return await optimizer.analyze(
        user_input, profile, plan,
        rag_context=template_rag,
        memory_context=combined_memory,
    )


async def save_pipeline_results(
    user_input: UserInput,
    run: PipelineRun,
) -> None:
    """Save memory + analysis record after pipeline completes."""
    if not run.result:
        return

    profile = run.result.talent_profile
    industry = run.result.industry_match
    plan = run.result.transition_plan

    # ── Update legacy memory (backward compat) ────────────────────
    try:
        legacy = await load_memory(user_input.user_id) or UserMemory(user_id=user_input.user_id)
        legacy.resume_text = user_input.resume_text
        legacy.background = user_input.background
        legacy.constraints = user_input.constraints
        legacy.last_profile_summary = profile.summary
        legacy.last_matched_industries = [m.industry for m in industry.top_matches]
        legacy.last_plan_target = f"{plan.chosen_target.industry} - {plan.chosen_target.role}"
        if user_input.target_direction:
            dirs = legacy.preferred_directions
            if user_input.target_direction not in dirs:
                dirs.append(user_input.target_direction)
            legacy.preferred_directions = dirs[-5:]
        await save_memory(legacy)
    except Exception as e:
        logger.warning(f"Failed to update legacy memory: {e}")

    # ── Save analysis record ──────────────────────────────────────
    try:
        record = AnalysisRecord(
            record_id=str(uuid.uuid4()),
            user_id=user_input.user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_input_json=user_input.model_dump_json(),
            pipeline_result_json=run.result.model_dump_json(),
        )
        await save_analysis(record)
    except Exception as e:
        logger.warning(f"Failed to save analysis record: {e}")

    # ── 3-layer memory extraction ─────────────────────────────────
    try:
        await extract_and_update_memory(
            user_id=user_input.user_id,
            user_input_json=user_input.model_dump_json(),
            pipeline_result_json=run.result.model_dump_json(),
        )
        logger.info(f"3-layer memory updated for user {user_input.user_id}")
    except Exception as e:
        logger.warning(f"Memory extraction failed (non-fatal): {e}")


# ── Full pipeline (non-interactive, for API use) ─────────────────

async def run_pipeline(user_input: UserInput, rag_context: str = "") -> PipelineRun:
    """Execute the 4-agent analysis pipeline (non-interactive, all at once).

    For interactive step-by-step use, call run_step1..run_step4 individually.
    """
    run = PipelineRun()
    t_start = time.monotonic()
    feedback_history: list[dict] = []

    memory_context, _, kb = await load_pipeline_context(user_input)

    # Agent 1
    t0 = time.monotonic()
    try:
        profile = await run_step1(user_input, memory_context, feedback_history, kb)
        run.profile = profile
        run.steps.append(StepResult("能力画像专家", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("能力画像专家", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 1 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # Agent 2
    t0 = time.monotonic()
    try:
        industry = await run_step2(user_input, profile, memory_context, feedback_history, kb, rag_context)
        run.industry_match = industry
        run.steps.append(StepResult("市场匹配引擎", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("市场匹配引擎", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 2 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # Agent 3
    t0 = time.monotonic()
    try:
        plan = await run_step3(user_input, profile, industry, memory_context, feedback_history, kb)
        run.transition_plan = plan
        run.steps.append(StepResult("路径规划架构师", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("路径规划架构师", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 3 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # Agent 4
    t0 = time.monotonic()
    try:
        resume = await run_step4(user_input, profile, plan, memory_context, feedback_history, kb)
        run.polished_resume = resume
        run.steps.append(StepResult("简历润色助手", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("简历润色助手", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 4 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # Assemble
    run.result = PipelineResult(
        talent_profile=profile,
        industry_match=industry,
        transition_plan=plan,
        polished_resume=resume,
    )
    run.total_duration_s = time.monotonic() - t_start

    await save_pipeline_results(user_input, run)
    return run


# ── Interactive pipeline (step-by-step with user feedback) ───────

@dataclass
class InteractivePipelineState:
    """Tracks state for interactive pipeline execution."""
    user_input: UserInput
    memory_context: str
    kb: KnowledgeStore
    feedback_history: list[dict] = field(default_factory=list)
    
    # Results from each step
    profile: TalentProfile | None = None
    industry_match: IndustryMatch | None = None
    transition_plan: TransitionPlan | None = None
    polished_resume: PolishedResume | None = None
    
    # Timing
    steps: list[StepResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)


async def init_interactive_pipeline(user_input: UserInput) -> InteractivePipelineState:
    """Initialize interactive pipeline state."""
    memory_context, _, kb = await load_pipeline_context(user_input)
    return InteractivePipelineState(
        user_input=user_input,
        memory_context=memory_context,
        kb=kb,
    )


async def run_interactive_step(
    state: InteractivePipelineState,
    step: int,
    user_feedback: str = "",
) -> tuple[bool, any, str]:
    """Run a single agent step in interactive mode.
    
    Args:
        state: Current pipeline state
        step: Step number (1-4)
        user_feedback: User's feedback from previous step (optional)
    
    Returns:
        (success, result, error_message)
    """
    # Add user feedback to history if provided
    if user_feedback and state.steps:
        last_agent = state.steps[-1].agent
        state.feedback_history.append({
            "agent": last_agent,
            "feedback": user_feedback,
        })
    
    t0 = time.monotonic()
    
    try:
        if step == 1:
            result = await run_step1(
                state.user_input,
                state.memory_context,
                state.feedback_history,
                state.kb,
            )
            state.profile = result
            state.steps.append(StepResult("能力画像专家", time.monotonic() - t0, True))
            return True, result, ""
        
        elif step == 2:
            if not state.profile:
                return False, None, "Step 1 must complete before step 2"
            result = await run_step2(
                state.user_input,
                state.profile,
                state.memory_context,
                state.feedback_history,
                state.kb,
            )
            state.industry_match = result
            state.steps.append(StepResult("市场匹配引擎", time.monotonic() - t0, True))
            return True, result, ""
        
        elif step == 3:
            if not state.profile or not state.industry_match:
                return False, None, "Steps 1-2 must complete before step 3"
            result = await run_step3(
                state.user_input,
                state.profile,
                state.industry_match,
                state.memory_context,
                state.feedback_history,
                state.kb,
            )
            state.transition_plan = result
            state.steps.append(StepResult("路径规划架构师", time.monotonic() - t0, True))
            return True, result, ""
        
        elif step == 4:
            if not state.profile or not state.transition_plan:
                return False, None, "Steps 1-3 must complete before step 4"
            result = await run_step4(
                state.user_input,
                state.profile,
                state.transition_plan,
                state.memory_context,
                state.feedback_history,
                state.kb,
            )
            state.polished_resume = result
            state.steps.append(StepResult("简历润色助手", time.monotonic() - t0, True))
            return True, result, ""
        
        else:
            return False, None, f"Invalid step: {step} (must be 1-4)"
    
    except Exception as e:
        agent_name = ["", "能力画像专家", "市场匹配引擎", "路径规划架构师", "简历润色助手"][step]
        state.steps.append(StepResult(agent_name, time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent {step} failed: {e}")
        return False, None, str(e)


async def finalize_interactive_pipeline(state: InteractivePipelineState) -> PipelineRun:
    """Finalize interactive pipeline and save results."""
    run = PipelineRun(
        steps=state.steps,
        profile=state.profile,
        industry_match=state.industry_match,
        transition_plan=state.transition_plan,
        polished_resume=state.polished_resume,
        total_duration_s=time.monotonic() - state.start_time,
    )
    
    if state.profile and state.industry_match and state.transition_plan and state.polished_resume:
        run.result = PipelineResult(
            talent_profile=state.profile,
            industry_match=state.industry_match,
            transition_plan=state.transition_plan,
            polished_resume=state.polished_resume,
        )
        await save_pipeline_results(state.user_input, run)
    
    return run
