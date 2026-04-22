"""
FastAPI application — exposes the CareerChange Helper (转行帮) pipeline as REST API.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.schemas.models import UserInput, PipelineResult
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("转行帮 API starting...")
    yield
    logging.getLogger(__name__).info("Shutting down.")


app = FastAPI(
    title="转行帮 CareerChange Helper",
    description="Multi-Agent 转行助手 API — 从职场资产评估到简历精修",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "转行帮"}


@app.post("/api/analyze", response_model=PipelineResult)
async def analyze(user_input: UserInput):
    """Run the full 4-agent pipeline."""
    result = await run_pipeline(user_input)

    if not result.success:
        failed = [s for s in result.steps if not s.success]
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Pipeline failed at: {failed[0].agent}",
                "message": failed[0].error,
                "completed_steps": [s.agent for s in result.steps if s.success],
            },
        )

    return result.result


@app.post("/api/analyze/step/{step}")
async def analyze_step(step: int, user_input: UserInput):
    """Run a single agent step (1-4) for debugging/testing."""
    from src.agents import ProfileAnalyzer, MarketMatcher, StrategyArchitect, ContentOptimizer

    if step == 1:
        agent = ProfileAnalyzer()
        return (await agent.analyze(user_input)).model_dump()

    analyzer = ProfileAnalyzer()
    profile = await analyzer.analyze(user_input)
    if step == 2:
        matcher = MarketMatcher()
        return (await matcher.analyze(profile)).model_dump()

    matcher = MarketMatcher()
    industry = await matcher.analyze(profile)
    if step == 3:
        architect = StrategyArchitect()
        return (await architect.analyze(profile, industry)).model_dump()

    architect = StrategyArchitect()
    plan = await architect.analyze(profile, industry)
    if step == 4:
        optimizer = ContentOptimizer()
        return (await optimizer.analyze(user_input, profile, plan)).model_dump()

    raise HTTPException(status_code=400, detail="Step must be 1-4")
