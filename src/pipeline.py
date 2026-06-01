"""
Pipeline — orchestrates the 5-agent analysis workflow with 3-layer persistent memory + RAG.

SEQUENTIAL INTERACTIVE MODE (default):
    Agent 1 → user confirms → Agent 2 → user confirms → ... → Agent 5

Each agent receives:
  - Its own inputs (structured data from previous agents)
  - Per-agent memory slice (profile / snapshot / preferences / events — not full dump)
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
    save_analysis, init_db,
    save_snapshot,
    load_session,
)
from src.memory.models import AnalysisRecord
from src.memory.extractor import extract_and_update_memory
from src.memory.context import build_agent_memory
from src.memory.snapshot import build_analysis_snapshot
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

AGENT_MEMORY_KEYS = {
    1: "profile_analyzer",
    2: "market_matcher",
    3: "strategy_architect",
    4: "cv_optimizer",
}


async def _build_step_memory(
    user_id: str,
    step: int,
    feedback_history: list[dict],
) -> str:
    """Build per-agent memory + in-run feedback for one pipeline step."""
    agent_key = AGENT_MEMORY_KEYS.get(step, "")
    base = await build_agent_memory(agent_key, user_id) if agent_key else ""
    feedback_ctx = _build_feedback_context(feedback_history)
    return "\n\n".join(filter(None, [base, feedback_ctx]))


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

async def load_pipeline_context(user_input: UserInput) -> KnowledgeStore:
    """Initialize DB and knowledge store. Memory is loaded per-agent at each step."""
    await init_db()
    return KnowledgeStore()


async def run_step1(
    user_input: UserInput,
    feedback_history: list[dict],
    kb: KnowledgeStore,
) -> TalentProfile:
    """Agent 1: 能力画像专家"""
    combined_memory = await _build_step_memory(user_input.user_id, 1, feedback_history)

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
    feedback_history: list[dict],
    kb: KnowledgeStore,
    rag_context: str = "",
) -> IndustryMatch:
    """Agent 2: 市场匹配引擎"""
    combined_memory = await _build_step_memory(user_input.user_id, 2, feedback_history)

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
    feedback_history: list[dict],
    kb: KnowledgeStore,
) -> TransitionPlan:
    """Agent 3: 路径规划架构师"""
    combined_memory = await _build_step_memory(user_input.user_id, 3, feedback_history)

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
    feedback_history: list[dict],
    kb: KnowledgeStore,
) -> PolishedResume:
    """Agent 4: 简历润色助手"""
    combined_memory = await _build_step_memory(user_input.user_id, 4, feedback_history)

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

    # ── Save analysis record ──────────────────────────────────────
    record_id = ""
    try:
        record = AnalysisRecord(
            record_id=str(uuid.uuid4()),
            user_id=user_input.user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_input_json=user_input.model_dump_json(),
            pipeline_result_json=run.result.model_dump_json(),
        )
        record_id = record.record_id
        await save_analysis(record)
    except Exception as e:
        logger.warning(f"Failed to save analysis record: {e}")

    # ── 3-layer memory extraction (before snapshot links analysis_id) ─
    try:
        await extract_and_update_memory(
            user_id=user_input.user_id,
            user_input_json=user_input.model_dump_json(),
            pipeline_result_json=run.result.model_dump_json(),
        )
        logger.info(f"3-layer memory updated for user {user_input.user_id}")
    except Exception as e:
        logger.warning(f"Memory extraction failed (non-fatal): {e}")

    # ── Compressed snapshot + profile link ────────────────────────
    if record_id:
        try:
            snapshot = build_analysis_snapshot(
                user_input.user_id,
                record_id,
                user_input,
                run.result,
            )
            await save_snapshot(snapshot)
        except Exception as e:
            logger.warning(f"Failed to save analysis snapshot: {e}")


# ── Full pipeline (non-interactive, for API use) ─────────────────

async def run_pipeline(user_input: UserInput, rag_context: str = "") -> PipelineRun:
    """Execute the 4-agent analysis pipeline (non-interactive, all at once).

    For interactive step-by-step use, call run_step1..run_step4 individually.
    """
    run = PipelineRun()
    t_start = time.monotonic()
    feedback_history: list[dict] = []

    kb = await load_pipeline_context(user_input)

    # Agent 1
    t0 = time.monotonic()
    try:
        profile = await run_step1(user_input, feedback_history, kb)
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
        industry = await run_step2(user_input, profile, feedback_history, kb, rag_context)
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
        plan = await run_step3(user_input, profile, industry, feedback_history, kb)
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
        resume = await run_step4(user_input, profile, plan, feedback_history, kb)
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
    kb = await load_pipeline_context(user_input)
    return InteractivePipelineState(
        user_input=user_input,
        kb=kb,
    )


async def restore_interactive_state_from_db(session_id: str) -> InteractivePipelineState | None:
    """Rebuild in-memory interactive state from SQLite (server restart / multi-worker recovery).

    Only restores sessions with status ``active``. Parsed agent outputs and ``steps`` are
    reconstructed from ``results_json``; ``feedback_history`` cannot be restored (demo OK).
    """
    row = await load_session(session_id)
    if not row:
        return None

    try:
        user_input = UserInput.model_validate(row["user_input"])
    except Exception:
        logger.exception("restore_interactive_state_from_db: invalid user_input for %s", session_id)
        return None

    results = row.get("results") or {}
    profile: TalentProfile | None = None
    industry_match: IndustryMatch | None = None
    transition_plan: TransitionPlan | None = None
    polished_resume: PolishedResume | None = None
    rebuilt_steps: list[StepResult] = []

    for step in (1, 2, 3, 4):
        key = str(step)
        if key not in results:
            break
        entry = results[key]
        if not isinstance(entry, dict):
            logger.warning("restore_interactive_state_from_db: bad entry type step %s", key)
            return None
        agent_name = entry.get("agent_name", "")
        duration_s = float(entry.get("duration_s") or 0.0)
        raw = entry.get("result")
        if raw is None:
            logger.warning("restore_interactive_state_from_db: missing result step %s", key)
            return None
        try:
            if step == 1:
                profile = TalentProfile.model_validate(raw)
            elif step == 2:
                industry_match = IndustryMatch.model_validate(raw)
            elif step == 3:
                transition_plan = TransitionPlan.model_validate(raw)
            elif step == 4:
                polished_resume = PolishedResume.model_validate(raw)
        except Exception:
            logger.exception(
                "restore_interactive_state_from_db: invalid result for step %s session %s",
                key,
                session_id,
            )
            return None
        rebuilt_steps.append(StepResult(agent_name, duration_s, True))

    kb = await load_pipeline_context(user_input)
    state = InteractivePipelineState(
        user_input=user_input,
        kb=kb,
    )
    state.profile = profile
    state.industry_match = industry_match
    state.transition_plan = transition_plan
    state.polished_resume = polished_resume
    state.steps = rebuilt_steps
    return state


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
