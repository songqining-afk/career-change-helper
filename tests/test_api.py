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
        resp = await client.post("/api/analyze", json=)
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
async def test_interview_status_not_found():
    """Non-existent session should return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/interview/nonexistent")
    assert resp.status_code == 404
