"""
FastAPI application — exposes the CareerChange Helper (转行帮) pipeline as REST API.

Endpoints:
  POST /api/analyze              — Run 4-agent analysis pipeline
  POST /api/analyze/step/{step}  — Run single agent (1-4) for debugging
  POST /api/interview/start      — Start multi-turn mock interview
  POST /api/interview/reply      — Submit answer, get feedback + next question
  GET  /api/interview/{id}       — Get interview session status/report
  GET  /api/memory/{user_id}     — Get user memory/profile
  GET  /api/memory/{user_id}/history — Get analysis history
  GET  /health                   — Health check
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi import UploadFile, File, Form

from src.schemas.models import (
    UserInput, PipelineResult, InterviewSession, InterviewQuestion,
    AnswerFeedback, InterviewReport,
)
from src.pipeline import (
    run_pipeline,
    init_interactive_pipeline,
    run_interactive_step,
    finalize_interactive_pipeline,
    InteractivePipelineState,
)
from src.agents.interview_simulator import InterviewSimulator
from src import interview_store
from src.memory.database import (
    init_db, load_memory, list_analyses,
    load_profile, save_profile, load_preferences, save_preference,
    delete_preference, list_events,
    save_session, load_session, get_active_session, abandon_session,
)
from src.memory.models import UserProfile, UserPreference, PreferenceSource
from src.knowledge import KnowledgeStore, extract_text, chunk_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


knowledge_store = KnowledgeStore()

UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("转行帮 API starting...")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="转行帮 CareerChange Helper",
    description="Multi-Agent 转行助手 API — 分析 + 模拟面试 + 持久记忆",
    version="0.2.1",
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
    return {"status": "ok", "service": "转行帮", "version": "0.2.1"}


# ── Analysis Pipeline (Agents 1-4) ─────────────────────────────────

@app.post("/api/analyze", response_model=PipelineResult)
async def analyze(user_input: UserInput):
    """Run the 4-agent analysis pipeline with memory integration (non-interactive)."""
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


# ── Interactive Pipeline (step-by-step with user feedback) ─────────

# In-memory state store (for demo; use Redis/DB in production)
_interactive_sessions: dict[str, InteractivePipelineState] = {}


class InteractiveStartRequest(BaseModel):
    user_input: UserInput


class InteractiveStartResponse(BaseModel):
    session_id: str
    message: str


@app.post("/api/analyze/interactive/start", response_model=InteractiveStartResponse)
async def interactive_start(req: InteractiveStartRequest):
    """Initialize an interactive pipeline session."""
    state = await init_interactive_pipeline(req.user_input)
    session_id = uuid.uuid4().hex[:12]
    _interactive_sessions[session_id] = state

    # Save to DB for progress recovery
    await save_session(
        session_id=session_id,
        user_id=req.user_input.user_id or "default",
        user_input=req.user_input.model_dump(),
        current_step=1,
        results={},
        status="active",
    )

    return InteractiveStartResponse(
        session_id=session_id,
        message="Interactive pipeline initialized. Call /api/analyze/interactive/step to proceed.",
    )


class InteractiveStepRequest(BaseModel):
    session_id: str
    step: int = Field(ge=1, le=4, description="Agent step (1-4)")
    user_feedback: str = Field(default="", description="User feedback from previous step")


class InteractiveStepResponse(BaseModel):
    success: bool
    step: int
    agent_name: str
    result: dict | None = None
    error: str = ""
    duration_s: float = 0.0


@app.post("/api/analyze/interactive/step", response_model=InteractiveStepResponse)
async def interactive_step(req: InteractiveStepRequest):
    """Run a single agent step in interactive mode."""
    state = _interactive_sessions.get(req.session_id)
    if not state:
        raise HTTPException(404, "Interactive session not found")

    agent_names = ["", "能力画像专家", "市场匹配引擎", "路径规划架构师", "简历润色助手"]

    success, result, error = await run_interactive_step(state, req.step, req.user_feedback)

    duration = state.steps[-1].duration_s if state.steps else 0.0

    # Auto-save progress to DB after each successful step
    if success and result:
        db_session = await load_session(req.session_id)
        if db_session:
            saved_results = db_session["results"]
            saved_results[str(req.step)] = {
                "agent_name": agent_names[req.step],
                "result": result.model_dump() if hasattr(result, 'model_dump') else result,
                "duration_s": duration,
            }
            await save_session(
                session_id=req.session_id,
                user_id=db_session["user_id"],
                user_input=db_session["user_input"],
                current_step=req.step,
                results=saved_results,
                status="active",
            )

    return InteractiveStepResponse(
        success=success,
        step=req.step,
        agent_name=agent_names[req.step],
        result=result.model_dump() if result else None,
        error=error,
        duration_s=duration,
    )


class InteractiveFinalizeResponse(BaseModel):
    success: bool
    total_duration_s: float
    result: PipelineResult | None = None


@app.post("/api/analyze/interactive/finalize", response_model=InteractiveFinalizeResponse)
async def interactive_finalize(session_id: str):
    """Finalize interactive pipeline and save results."""
    state = _interactive_sessions.get(session_id)
    if not state:
        raise HTTPException(404, "Interactive session not found")

    run = await finalize_interactive_pipeline(state)

    # Mark session as completed in DB
    db_session = await load_session(session_id)
    if db_session:
        await save_session(
            session_id=session_id,
            user_id=db_session["user_id"],
            user_input=db_session["user_input"],
            current_step=4,
            results=db_session["results"],
            status="completed",
        )

    # Clean up session
    del _interactive_sessions[session_id]

    return InteractiveFinalizeResponse(
        success=run.success,
        total_duration_s=run.total_duration_s,
        result=run.result,
    )


@app.delete("/api/analyze/interactive/{session_id}")
async def interactive_cancel(session_id: str):
    """Cancel an interactive pipeline session."""
    if session_id in _interactive_sessions:
        del _interactive_sessions[session_id]
    await abandon_session(session_id)
    return {"session_id": session_id, "cancelled": True}


# ── Session Recovery ─────────────────────────────────────────────

@app.get("/api/session/active")
async def session_get_active(user_id: str = Query(default="default")):
    """Get the most recent active (unfinished) session for a user."""
    session = await get_active_session(user_id)
    if not session:
        return {"exists": False}
    return {"exists": True, "session": session}


@app.delete("/api/session/{session_id}")
async def session_abandon(session_id: str):
    """Abandon a session (mark as abandoned)."""
    deleted = await abandon_session(session_id)
    if not deleted:
        raise HTTPException(404, "Session not found or already completed")
    if session_id in _interactive_sessions:
        del _interactive_sessions[session_id]
    return {"session_id": session_id, "abandoned": True}


# ── Single-step debugging endpoint (legacy) ─────────────────────────


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
    question = await interviewer.start(session, industry, resume, user_id=req.user_input.user_id)

    # Persist
    interview_store.save(session, industry, resume, user_id=req.user_input.user_id)

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
    result = await interviewer.reply(session, req.answer, data.industry, data.resume, user_id=data.user_id)

    # Save updated session
    interview_store.save(session, data.industry, data.resume, user_id=data.user_id)

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


# ── Memory (3-Layer: Profile + Events + Preferences) ──────────────────

@app.get("/api/memory/{user_id}")
async def memory_get(user_id: str):
    """Get user's complete 3-layer memory."""
    profile = await load_profile(user_id)
    prefs = await load_preferences(user_id)
    events = await list_events(user_id, limit=20)
    legacy = await load_memory(user_id)

    return {
        "user_id": user_id,
        "has_profile": profile is not None,
        "profile": profile.model_dump() if profile else None,
        "preferences": [p.model_dump() for p in prefs],
        "recent_events": [e.model_dump() for e in events],
        "legacy_memory": legacy.model_dump() if legacy else None,
    }


@app.get("/api/memory/{user_id}/profile")
async def memory_profile_get(user_id: str):
    """Get user's structured profile (Layer 1)."""
    profile = await load_profile(user_id)
    if not profile:
        return {"user_id": user_id, "exists": False}
    return {"user_id": user_id, "exists": True, "profile": profile.model_dump()}


class ProfileUpdateRequest(BaseModel):
    """Manual profile update — user can correct any field."""
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    city: str | None = None
    education: str | None = None
    years_of_experience: int | None = None
    current_role: str | None = None
    current_industry: str | None = None
    current_salary_range: str | None = None
    family_situation: str | None = None
    target_direction: str | None = None
    transition_stage: str | None = None
    confidence_level: str | None = None


@app.put("/api/memory/{user_id}/profile")
async def memory_profile_update(user_id: str, req: ProfileUpdateRequest):
    """Manually update user profile fields. Only non-null fields are updated."""
    profile = await load_profile(user_id) or UserProfile(user_id=user_id)

    for field_name, value in req.model_dump(exclude_none=True).items():
        setattr(profile, field_name, value)

    await save_profile(profile)
    return {"user_id": user_id, "updated": True, "profile": profile.model_dump()}


@app.get("/api/memory/{user_id}/events")
async def memory_events_get(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    event_type: str = Query(default="", description="Filter: analysis|interview|direction|milestone|feedback"),
):
    """Get user's event timeline (Layer 2)."""
    events = await list_events(user_id, limit=limit, event_type=event_type)
    return {
        "user_id": user_id,
        "count": len(events),
        "events": [e.model_dump() for e in events],
    }


@app.get("/api/memory/{user_id}/preferences")
async def memory_prefs_get(user_id: str):
    """Get user's preferences (Layer 3)."""
    prefs = await load_preferences(user_id)
    return {
        "user_id": user_id,
        "count": len(prefs),
        "preferences": [p.model_dump() for p in prefs],
    }


class PreferenceAddRequest(BaseModel):
    key: str = Field(description="industry|role|location|salary|workstyle|rejection")
    value: str
    source: str = Field(default="explicit", description="explicit|inferred")


@app.post("/api/memory/{user_id}/preferences")
async def memory_prefs_add(user_id: str, req: PreferenceAddRequest):
    """Add a user preference."""
    pref = UserPreference(
        user_id=user_id,
        key=req.key,
        value=req.value,
        source=PreferenceSource(req.source),
        confidence=1.0 if req.source == "explicit" else 0.7,
    )
    await save_preference(pref)
    return {"user_id": user_id, "added": True, "preference": pref.model_dump()}


@app.delete("/api/memory/{user_id}/preferences")
async def memory_prefs_delete(
    user_id: str,
    key: str = Query(...),
    value: str = Query(...),
):
    """Delete a specific preference."""
    deleted = await delete_preference(user_id, key, value)
    if not deleted:
        raise HTTPException(404, "偏好不存在")
    return {"user_id": user_id, "deleted": True}


@app.get("/api/memory/{user_id}/history")
async def memory_history(user_id: str, limit: int = Query(default=10, ge=1, le=50)):
    """Get user's analysis history."""
    records = await list_analyses(user_id, limit)
    return {
        "user_id": user_id,
        "count": len(records),
        "records": [r.model_dump() for r in records],
    }


# ── Knowledge Base (RAG) ─────────────────────────────────────────

@app.post("/api/knowledge/upload")
async def knowledge_upload(
    file: UploadFile = File(...),
    user_id: str = Form(default="default"),
    doc_type: str = Form(default="resume", description="resume|industry|jd|interview|template"),
):
    """Upload a document → extract text → chunk → store in vector DB.

    doc_type controls metadata tagging:
      - resume: 用户简历
      - industry: 行业报告/资料
      - jd: 岗位JD
      - interview: 面试题库
      - template: 优秀简历模板
    """
    allowed = {".pdf", ".txt", ".md", ".markdown"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"不支持的文件类型: {suffix}，请上传 {', '.join(allowed)}")

    # Save to disk
    save_path = UPLOAD_DIR / user_id
    save_path.mkdir(parents=True, exist_ok=True)
    dest = save_path / file.filename
    content = await file.read()
    dest.write_bytes(content)

    # Extract + chunk
    try:
        text = extract_text(dest)
    except Exception as e:
        raise HTTPException(400, f"文件解析失败: {e}")

    chunks = chunk_text(text, chunk_size=500, overlap=50)
    if not chunks:
        raise HTTPException(400, "文件内容为空，无法提取文本")

    # Tag filename with doc_type for retrieval filtering
    tagged_filename = f"[{doc_type}]{file.filename}"

    count = knowledge_store.add_document(user_id, tagged_filename, chunks)
    logger.info(f"Uploaded {file.filename} ({doc_type}) for {user_id}: {count} chunks")

    return {
        "filename": file.filename,
        "doc_type": doc_type,
        "chunks": count,
        "user_id": user_id,
    }


@app.get("/api/knowledge/documents")
async def knowledge_list(user_id: str = Query(default="default")):
    """List all documents in user's knowledge base."""
    docs = knowledge_store.list_documents(user_id)
    return {"user_id": user_id, "documents": docs}


@app.delete("/api/knowledge/{filename}")
async def knowledge_delete(filename: str, user_id: str = Query(default="default")):
    """Delete a document from user's knowledge base."""
    count = knowledge_store.delete_document(user_id, filename)
    if count == 0:
        raise HTTPException(404, f"文档 '{filename}' 不存在")
    return {"deleted": filename, "chunks_removed": count}


class SearchRequest(BaseModel):
    query: str
    user_id: str = "default"
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: str = Field(default="", description="Filter by doc_type: resume|industry|jd|interview|template")


@app.post("/api/knowledge/search")
async def knowledge_search(req: SearchRequest):
    """Search user's knowledge base with optional doc_type filter."""
    hits = knowledge_store.search(req.user_id, req.query, top_k=req.top_k)

    # Filter by doc_type if specified
    if req.doc_type:
        prefix = f"[{req.doc_type}]"
        hits = [h for h in hits if h["filename"].startswith(prefix)]

    return {"query": req.query, "results": hits}


# ── Static Files (serve built frontend) ─────────────────────────────
# Mount static assets first, then catch-all for SPA routing

WEB_DIST = Path(__file__).parent.parent / "web" / "dist"
if WEB_DIST.exists():
    from fastapi.responses import FileResponse

    # Mount /assets before catch-all route
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    # Serve root index.html
    @app.get("/")
    async def serve_root():
        return FileResponse(WEB_DIST / "index.html")

    # Catch-all for SPA routing (must be last)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA — try static file first, fallback to index.html."""
        file_path = WEB_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(WEB_DIST / "index.html")
