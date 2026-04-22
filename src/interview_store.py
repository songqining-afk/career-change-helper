"""In-memory session store for interview sessions. Swap for Redis later."""

from __future__ import annotations

from src.schemas.models import InterviewSession, IndustryMatch, PolishedResume


class _SessionData:
    """Bundles session + the context it needs from earlier agents."""
    __slots__ = ("session", "industry", "resume")

    def __init__(
        self, session: InterviewSession,
        industry: IndustryMatch, resume: PolishedResume,
    ):
        self.session = session
        self.industry = industry
        self.resume = resume


# Simple dict store — single-process only
_store: dict[str, _SessionData] = {}


def save(session: InterviewSession, industry: IndustryMatch, resume: PolishedResume) -> None:
    _store[session.session_id] = _SessionData(session, industry, resume)


def get(session_id: str) -> _SessionData | None:
    return _store.get(session_id)


def delete(session_id: str) -> None:
    _store.pop(session_id, None)


def list_sessions() -> list[str]:
    return list(_store.keys())
