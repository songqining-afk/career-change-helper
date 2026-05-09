"""In-memory session store for interview sessions. Swap for Redis later."""

from __future__ import annotations

from src.schemas.models import InterviewSession, IndustryMatch, PolishedResume


class _SessionData:
    """Bundles session + the context it needs from earlier agents."""
    __slots__ = ("session", "industry", "resume", "user_id")

    def __init__(
        self, session: InterviewSession,
        industry: IndustryMatch, resume: PolishedResume,
        user_id: str = "default",
    ):
        self.session = session
        self.industry = industry
        self.resume = resume
        self.user_id = user_id


# Simple dict store — single-process only
_store: dict[str, _SessionData] = {}


def save(
    session: InterviewSession, industry: IndustryMatch,
    resume: PolishedResume, user_id: str = "default",
) -> None:
    _store[session.session_id] = _SessionData(session, industry, resume, user_id)


def get(session_id: str) -> _SessionData | None:
    return _store.get(session_id)


def delete(session_id: str) -> None:
    _store.pop(session_id, None)


def list_sessions() -> list[str]:
    return list(_store.keys())
