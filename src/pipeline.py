"""
Pipeline — orchestrates the 4-agent workflow.

    UserInput → ProfileAnalyzer → MarketMatcher → StrategyArchitect → CVOptimizer
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from src.agents import ProfileAnalyzer, MarketMatcher, StrategyArchitect, CVOptimizer
from src.schemas.models import (
    UserInput, TalentProfile, IndustryMatch,
    TransitionPlan, PolishedResume, PipelineResult,
)

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
    total_duration_s: float = 0.0

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)


async def run_pipeline(user_input: UserInput) -> PipelineRun:
    """Execute the full 4-agent pipeline sequentially."""
    run = PipelineRun()
    t_start = time.monotonic()

    # ── Agent 1: 能力画像专家 (Profile Analyzer) ────────────────
    t0 = time.monotonic()
    try:
        analyzer = ProfileAnalyzer()
        profile = await analyzer.analyze(user_input)
        run.steps.append(StepResult("能力画像专家", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("能力画像专家", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 1 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # ── Agent 2: 市场匹配引擎 (Market Matcher) ─────────────────
    t0 = time.monotonic()
    try:
        matcher = MarketMatcher()
        industry = await matcher.analyze(profile)
        run.steps.append(StepResult("市场匹配引擎", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("市场匹配引擎", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 2 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # ── Agent 3: 路径规划架构师 (Strategy Architect) ────────────
    t0 = time.monotonic()
    try:
        architect = StrategyArchitect()
        plan = await architect.analyze(profile, industry)
        run.steps.append(StepResult("路径规划架构师", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("路径规划架构师", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 3 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    # ── Agent 4: 简历润色助手 (CV Optimizer) ────────────────────
    t0 = time.monotonic()
    try:
        optimizer = CVOptimizer()
        resume = await optimizer.analyze(user_input, profile, plan)
        run.steps.append(StepResult("简历润色助手", time.monotonic() - t0, True))
    except Exception as e:
        run.steps.append(StepResult("简历润色助手", time.monotonic() - t0, False, str(e)))
        logger.error(f"Agent 4 failed: {e}")
        run.total_duration_s = time.monotonic() - t_start
        return run

    run.result = PipelineResult(
        talent_profile=profile,
        industry_match=industry,
        transition_plan=plan,
        polished_resume=resume,
    )
    run.total_duration_s = time.monotonic() - t_start
    logger.info(f"Pipeline complete in {run.total_duration_s:.1f}s")
    return run
