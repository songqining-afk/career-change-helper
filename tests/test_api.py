"""Tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from src.app import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "转行帮"


@pytest.mark.asyncio
async def test_analyze_validation_error():
    """Missing required field should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_interview_start_validation_error():
    """Missing user_input should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/interview/start", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_interview_reply_not_found():
    """Non-existent session should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/interview/reply", json={
            "session_id": "nonexistent",
            "answer": "test",
        })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_interactive_finalize_unknown_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze/interactive/finalize",
            params={"session_id": "nosuchsession"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_interactive_finalize_requires_session_id_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze/interactive/finalize")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_interactive_finalize_rejects_incomplete_pipeline():
    """Start session but do not run any agent steps — finalize must return 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start = await client.post(
            "/api/analyze/interactive/start",
            json={
                "user_input": {
                    "user_id": "test-user",
                    "resume_text": "Engineer with 5 years Python experience.",
                    "background": "",
                    "constraints": "",
                    "target_direction": "",
                }
            },
        )
        assert start.status_code == 200
        session_id = start.json()["session_id"]
        resp = await client.post(
            "/api/analyze/interactive/finalize",
            params={"session_id": session_id},
        )
    assert resp.status_code == 400
