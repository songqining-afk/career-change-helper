"""
FastAPI application — exposes the CareerChange Helper (转行帮) pipeline as REST API.

Endpoints:
  POST /api/analyze              — Run 4-agent analysis pipeline
  POST /api/analyze/step/{step}  — Run single agent (1-4) for debugging
  POST /api/interview/start      — Start multi-turn mock interview
  POST /api/interview/reply      — Submit answer, get feedback + next question
  GET  /api/interview/{id}       — Get interview session status/report
  GET  /health                   — Health check
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.schemas.models import (
    UserInput, PipelineResult, InterviewSession, InterviewQuestion,
    AnswerFeedback, InterviewReport,
)
from src.pipeline import run_pipeline
from src.agents.interview_simulator import InterviewSimulator
from src import interview_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("转行帮 API starting...")
    yield
    logging.getLogger(__name__).info("Shutting down.")


app = FastAPI(
    title="转行帮 CareerChange Helper",
    description="Multi-Agent 转行助手 API — 分析 + 模拟面试",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "转行帮"}


# ── Analysis Pipeline (Agents 1-4) ─────────────────────────────────

@app.post("/api/analyze", response_model=PipelineResult)
async def analyze(user_input: UserInput):
    """Run the 4-agent analysis pipeline."""
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
    from src.agents import ProfileAnalyzer, MarketMatcher, StrategyArchitect, CVOptimizer

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
        optimizer = CVOptimizer()
        return (await optimizer.analyze(user_input, profile, plan)).model_dump()

    raise HTTPException(status_code=400, detail="Step must be 1-4")


# ── Interview (Agent 5 — Multi-turn) ───────────────────────────────

class InterviewStartRequest(BaseModel):
    """Start a mock interview using pipeline results."""
    user_input: UserInput
    pipeline_result: PipelineResult | None = Field(
        default=None,
        description="If provided, skip re-running pipeline. Otherwise runs pipeline first.",
    )

class InterviewStartResponse(BaseModel):
    session_id: str
    interviewer_persona: str
    question: InterviewQuestion
    round: int
    total_rounds: int = 3

class InterviewReplyRequest(BaseModel):
    session_id: str
    answer: str

class InterviewReplyResponse(BaseModel):
    feedback: AnswerFeedback
    next_question: InterviewQuestion | None = None
    round: int
    is_final: bool = False
    report: InterviewReport | None = None


@app.post("/api/interview/start", response_model=InterviewStartResponse)
async def interview_start(req: InterviewStartRequest):
    """Start a multi-turn mock interview session."""
    # Get industry + resume data
    if req.pipeline_result:
        from src.schemas.models import IndustryMatch, PolishedResume
        industry = req.pipeline_result.industry_match
        resume = req.pipeline_result.polished_resume
    else:
        result = await run_pipeline(req.user_input)
        if not result.success:
            raise HTTPException(status_code=500, detail="Pipeline failed, cannot start interview")
        industry = result.industry_match
        resume = result.polished_resume

    # Create session
    session_id = uuid.uuid4().hex[:12]
    top = industry.top_matches[0] if industry.top_matches else None
    session = InterviewSession(
        session_id=session_id,
        target_role=top.role if top else "未知",
        target_industry=top.industry if top else "未知",
    )

    # Generate first question
    interviewer = InterviewSimulator()
    question = await interviewer.start(session, industry, resume)

    # Persist
    interview_store.save(session, industry, resume)

    return InterviewStartResponse(
        session_id=session_id,
        interviewer_persona=session.interviewer_persona,
        question=question,
        round=1,
    )


@app.post("/api/interview/reply", response_model=InterviewReplyResponse)
async def interview_reply(req: InterviewReplyRequest):
    """Submit an answer to the current interview question."""
    data = interview_store.get(req.session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Interview session not found")

    session = data.session
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")

    interviewer = InterviewSimulator()
    result = await interviewer.reply(session, req.answer, data.industry, data.resume)

    # Save updated session
    interview_store.save(session, data.industry, data.resume)

    if isinstance(result, InterviewReport):
        # Final round — return report
        return InterviewReplyResponse(
            feedback=session.turns[-1].feedback,
            round=3,
            is_final=True,
            report=result,
        )
    else:
        # More rounds to go
        next_q = session.turns[-1].question if session.turns else None
        return InterviewReplyResponse(
            feedback=result,
            next_question=next_q,
            round=session.current_round,
            is_final=False,
        )


@app.get("/api/interview/{session_id}")
async def interview_status(session_id: str):
    """Get interview session status and history."""
    data = interview_store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Interview session not found")

    return data.session.model_dump()
