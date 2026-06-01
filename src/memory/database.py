"""
Async SQLite database layer for the 3-layer persistent memory system.

Tables:
  - user_memory      (legacy, kept for backward compat)
  - analysis_records  (legacy)
  - user_profiles     (Layer 1: 结构化档案)
  - memory_events     (Layer 2: 事件流)
  - user_preferences  (Layer 3: 偏好)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from src.memory.models import (
    UserMemory, AnalysisRecord,
    UserProfile, MemoryEvent, UserPreference, PreferenceSource,
    AnalysisSnapshot,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "memory.db"


# ── Init ─────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Legacy tables
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id TEXT PRIMARY KEY,
                resume_text TEXT DEFAULT '',
                background TEXT DEFAULT '',
                constraints TEXT DEFAULT '',
                preferred_directions TEXT DEFAULT '[]',
                last_profile_summary TEXT DEFAULT '',
                last_matched_industries TEXT DEFAULT '[]',
                last_plan_target TEXT DEFAULT '',
                interview_count INTEGER DEFAULT 0,
                avg_readiness_score REAL DEFAULT 0.0,
                recurring_gaps TEXT DEFAULT '[]',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analysis_records (
                record_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_input_json TEXT NOT NULL,
                pipeline_result_json TEXT NOT NULL,
                interview_report_json TEXT DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES user_memory(user_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_user
            ON analysis_records(user_id, timestamp DESC)
        """)

        # Layer 1: 用户档案
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                name TEXT DEFAULT '',
                age INTEGER DEFAULT 0,
                gender TEXT DEFAULT '',
                city TEXT DEFAULT '',
                education TEXT DEFAULT '',
                years_of_experience INTEGER DEFAULT 0,
                current_role TEXT DEFAULT '',
                current_industry TEXT DEFAULT '',
                current_salary_range TEXT DEFAULT '',
                family_situation TEXT DEFAULT '',
                core_strengths TEXT DEFAULT '[]',
                transferable_skills TEXT DEFAULT '[]',
                personality_tags TEXT DEFAULT '[]',
                recurring_gaps TEXT DEFAULT '[]',
                transition_stage TEXT DEFAULT 'exploring',
                target_direction TEXT DEFAULT '',
                confidence_level TEXT DEFAULT 'low',
                analysis_count INTEGER DEFAULT 0,
                interview_count INTEGER DEFAULT 0,
                avg_readiness_score REAL DEFAULT 0.0,
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
        """)

        # Layer 2: 事件流
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memory_events (
                event_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                summary TEXT DEFAULT '',
                details TEXT DEFAULT '',
                insights TEXT DEFAULT '[]'
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_user
            ON memory_events(user_id, timestamp DESC)
        """)

        # Layer 3: 偏好
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT DEFAULT 'explicit',
                confidence REAL DEFAULT 1.0,
                created_at TEXT DEFAULT '',
                PRIMARY KEY (user_id, key, value)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_prefs_user
            ON user_preferences(user_id)
        """)

        # Analysis snapshots — compressed cross-session memory
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analysis_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                analysis_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                target_direction TEXT DEFAULT '',
                top_industries TEXT DEFAULT '[]',
                top_roles TEXT DEFAULT '[]',
                strength_summary TEXT DEFAULT '',
                gap_summary TEXT DEFAULT '',
                plan_milestone TEXT DEFAULT '',
                user_constraints TEXT DEFAULT '',
                narrative TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_user
            ON analysis_snapshots(user_id, created_at DESC)
        """)

        await _migrate_schema(db)

        # Interactive sessions (progress save)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS interactive_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                user_input_json TEXT NOT NULL,
                current_step INTEGER DEFAULT 1,
                results_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_status
            ON interactive_sessions(user_id, status, updated_at DESC)
        """)

        await db.commit()
    logger.info("Memory database initialized at %s", DB_PATH)


async def _column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return any(row[1] == column for row in rows)


async def _migrate_schema(db: aiosqlite.Connection) -> None:
    """Add columns introduced after initial schema without breaking existing DBs."""
    migrations: list[tuple[str, str, str]] = [
        ("user_profiles", "previous_target_direction", "TEXT DEFAULT ''"),
        ("user_profiles", "last_analysis_id", "TEXT DEFAULT ''"),
        ("user_profiles", "last_snapshot_at", "TEXT DEFAULT ''"),
        ("user_preferences", "updated_at", "TEXT DEFAULT ''"),
        ("user_preferences", "times_seen", "INTEGER DEFAULT 1"),
    ]
    for table, column, typedef in migrations:
        if not await _column_exists(db, table, column):
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")


# ── Interactive Sessions (Progress Save) ─────────────────────────

async def save_session(
    session_id: str,
    user_id: str,
    user_input: dict,
    current_step: int,
    results: dict,
    status: str = "active",
) -> None:
    """Save or update an interactive session."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO interactive_sessions
                (session_id, user_id, user_input_json, current_step, results_json, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                current_step = excluded.current_step,
                results_json = excluded.results_json,
                status = excluded.status,
                updated_at = excluded.updated_at
        """, (
            session_id, user_id,
            json.dumps(user_input, ensure_ascii=False),
            current_step,
            json.dumps(results, ensure_ascii=False),
            status, now, now,
        ))
        await db.commit()


async def load_session(session_id: str, include_completed: bool = False) -> dict | None:
    """Load a session by ID.

    By default only returns rows with status ``active`` (unfinished flow).
    Set ``include_completed=True`` to load any status (e.g. after finalize).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if include_completed:
            cursor = await db.execute(
                "SELECT * FROM interactive_sessions WHERE session_id = ?",
                (session_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM interactive_sessions WHERE session_id = ? AND status = 'active'",
                (session_id,),
            )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "user_input": json.loads(row["user_input_json"]),
            "current_step": row["current_step"],
            "results": json.loads(row["results_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


async def get_active_session(user_id: str) -> dict | None:
    """Get the most recent active session for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM interactive_sessions WHERE user_id = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "user_input": json.loads(row["user_input_json"]),
            "current_step": row["current_step"],
            "results": json.loads(row["results_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


async def abandon_session(session_id: str) -> bool:
    """Mark a session as abandoned."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE interactive_sessions SET status = 'abandoned', updated_at = ? WHERE session_id = ? AND status = 'active'",
            (now, session_id),
        )
        await db.commit()
        return cursor.rowcount > 0


# ── Layer 1: UserProfile CRUD ────────────────────────────────────

async def save_profile(profile: UserProfile) -> None:
    """Upsert user profile."""
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    if not profile.created_at:
        profile.created_at = profile.updated_at

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_profiles (
                user_id, name, age, gender, city, education,
                years_of_experience, current_role, current_industry,
                current_salary_range, family_situation,
                core_strengths, transferable_skills, personality_tags,
                recurring_gaps, transition_stage, target_direction,
                previous_target_direction, confidence_level, analysis_count,
                interview_count, avg_readiness_score, last_analysis_id,
                last_snapshot_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                age = excluded.age,
                gender = excluded.gender,
                city = excluded.city,
                education = excluded.education,
                years_of_experience = excluded.years_of_experience,
                current_role = excluded.current_role,
                current_industry = excluded.current_industry,
                current_salary_range = excluded.current_salary_range,
                family_situation = excluded.family_situation,
                core_strengths = excluded.core_strengths,
                transferable_skills = excluded.transferable_skills,
                personality_tags = excluded.personality_tags,
                recurring_gaps = excluded.recurring_gaps,
                transition_stage = excluded.transition_stage,
                target_direction = excluded.target_direction,
                previous_target_direction = excluded.previous_target_direction,
                confidence_level = excluded.confidence_level,
                analysis_count = excluded.analysis_count,
                interview_count = excluded.interview_count,
                avg_readiness_score = excluded.avg_readiness_score,
                last_analysis_id = excluded.last_analysis_id,
                last_snapshot_at = excluded.last_snapshot_at,
                updated_at = excluded.updated_at
        """, (
            profile.user_id, profile.name, profile.age, profile.gender,
            profile.city, profile.education, profile.years_of_experience,
            profile.current_role, profile.current_industry,
            profile.current_salary_range, profile.family_situation,
            json.dumps(profile.core_strengths, ensure_ascii=False),
            json.dumps(profile.transferable_skills, ensure_ascii=False),
            json.dumps(profile.personality_tags, ensure_ascii=False),
            json.dumps(profile.recurring_gaps, ensure_ascii=False),
            profile.transition_stage, profile.target_direction,
            profile.previous_target_direction,
            profile.confidence_level, profile.analysis_count,
            profile.interview_count, profile.avg_readiness_score,
            profile.last_analysis_id, profile.last_snapshot_at,
            profile.created_at, profile.updated_at,
        ))
        await db.commit()


async def load_profile(user_id: str) -> UserProfile | None:
    """Load user profile. Returns None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return UserProfile(
                user_id=row["user_id"],
                name=row["name"],
                age=row["age"],
                gender=row["gender"],
                city=row["city"],
                education=row["education"],
                years_of_experience=row["years_of_experience"],
                current_role=row["current_role"],
                current_industry=row["current_industry"],
                current_salary_range=row["current_salary_range"],
                family_situation=row["family_situation"],
                core_strengths=json.loads(row["core_strengths"]),
                transferable_skills=json.loads(row["transferable_skills"]),
                personality_tags=json.loads(row["personality_tags"]),
                recurring_gaps=json.loads(row["recurring_gaps"]),
                transition_stage=row["transition_stage"],
                target_direction=row["target_direction"],
                previous_target_direction=row["previous_target_direction"] if "previous_target_direction" in row.keys() else "",
                confidence_level=row["confidence_level"],
                analysis_count=row["analysis_count"],
                interview_count=row["interview_count"],
                avg_readiness_score=row["avg_readiness_score"],
                last_analysis_id=row["last_analysis_id"] if "last_analysis_id" in row.keys() else "",
                last_snapshot_at=row["last_snapshot_at"] if "last_snapshot_at" in row.keys() else "",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )


# ── Layer 2: MemoryEvent CRUD ────────────────────────────────────

async def add_event(event: MemoryEvent) -> None:
    """Append an event to the timeline."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO memory_events
            (event_id, user_id, event_type, timestamp, summary, details, insights)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id, event.user_id, event.event_type.value,
            event.timestamp, event.summary, event.details,
            json.dumps(event.insights, ensure_ascii=False),
        ))
        await db.commit()


async def list_events(
    user_id: str, limit: int = 20, event_type: str = ""
) -> list[MemoryEvent]:
    """List recent events for a user, optionally filtered by type."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if event_type:
            sql = "SELECT * FROM memory_events WHERE user_id = ? AND event_type = ? ORDER BY timestamp DESC LIMIT ?"
            params = (user_id, event_type, limit)
        else:
            sql = "SELECT * FROM memory_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?"
            params = (user_id, limit)

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [
                MemoryEvent(
                    event_id=r["event_id"],
                    user_id=r["user_id"],
                    event_type=r["event_type"],
                    timestamp=r["timestamp"],
                    summary=r["summary"],
                    details=r["details"],
                    insights=json.loads(r["insights"]),
                )
                for r in rows
            ]


async def list_events_by_types(
    user_id: str,
    event_types: list[str],
    limit: int = 5,
) -> list[MemoryEvent]:
    """List recent events filtered by multiple event types."""
    if not event_types:
        return []
    placeholders = ",".join("?" * len(event_types))
    sql = (
        f"SELECT * FROM memory_events WHERE user_id = ? "
        f"AND event_type IN ({placeholders}) "
        f"ORDER BY timestamp DESC LIMIT ?"
    )
    params: tuple = (user_id, *event_types, limit)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [
                MemoryEvent(
                    event_id=r["event_id"],
                    user_id=r["user_id"],
                    event_type=r["event_type"],
                    timestamp=r["timestamp"],
                    summary=r["summary"],
                    details=r["details"],
                    insights=json.loads(r["insights"]),
                )
                for r in rows
            ]


# ── Analysis snapshots ───────────────────────────────────────────

async def save_snapshot(snapshot: AnalysisSnapshot) -> None:
    """Persist a compressed analysis snapshot and link it on the user profile."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO analysis_snapshots (
                snapshot_id, user_id, analysis_id, created_at,
                target_direction, top_industries, top_roles,
                strength_summary, gap_summary, plan_milestone,
                user_constraints, narrative
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.snapshot_id, snapshot.user_id, snapshot.analysis_id,
            snapshot.created_at, snapshot.target_direction,
            json.dumps(snapshot.top_industries, ensure_ascii=False),
            json.dumps(snapshot.top_roles, ensure_ascii=False),
            snapshot.strength_summary, snapshot.gap_summary,
            snapshot.plan_milestone, snapshot.user_constraints,
            snapshot.narrative,
        ))
        await db.commit()

    profile = await load_profile(snapshot.user_id)
    if profile:
        profile.last_analysis_id = snapshot.analysis_id
        profile.last_snapshot_at = snapshot.created_at
        await save_profile(profile)


async def get_latest_snapshot(user_id: str) -> AnalysisSnapshot | None:
    """Return the most recent analysis snapshot for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM analysis_snapshots WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return AnalysisSnapshot(
                snapshot_id=row["snapshot_id"],
                user_id=row["user_id"],
                analysis_id=row["analysis_id"],
                created_at=row["created_at"],
                target_direction=row["target_direction"],
                top_industries=json.loads(row["top_industries"]),
                top_roles=json.loads(row["top_roles"]),
                strength_summary=row["strength_summary"],
                gap_summary=row["gap_summary"],
                plan_milestone=row["plan_milestone"],
                user_constraints=row["user_constraints"],
                narrative=row["narrative"],
            )


# ── Layer 3: UserPreference CRUD ─────────────────────────────────

async def save_preference(pref: UserPreference) -> None:
    """Upsert a preference."""
    now = datetime.now(timezone.utc).isoformat()
    pref.created_at = pref.created_at or now
    pref.updated_at = now
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_preferences
                (user_id, key, value, source, confidence, created_at, updated_at, times_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, key, value) DO UPDATE SET
                source = excluded.source,
                confidence = MAX(excluded.confidence, user_preferences.confidence),
                updated_at = excluded.updated_at,
                times_seen = user_preferences.times_seen + 1
        """, (
            pref.user_id, pref.key, pref.value,
            pref.source.value if isinstance(pref.source, PreferenceSource) else pref.source,
            pref.confidence, pref.created_at, pref.updated_at, pref.times_seen,
        ))
        await db.commit()


async def load_preferences(user_id: str) -> list[UserPreference]:
    """Load all preferences for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_preferences WHERE user_id = ? ORDER BY confidence DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                UserPreference(
                    user_id=r["user_id"],
                    key=r["key"],
                    value=r["value"],
                    source=r["source"],
                    confidence=r["confidence"],
                    times_seen=r["times_seen"] if "times_seen" in r.keys() else 1,
                    created_at=r["created_at"],
                    updated_at=r["updated_at"] if "updated_at" in r.keys() else "",
                )
                for r in rows
            ]


async def load_preferences_filtered(
    user_id: str,
    keys: list[str],
    min_confidence: float = 0.6,
) -> list[UserPreference]:
    """Load preferences for specific keys; explicit always included, inferred filtered by confidence."""
    if not keys:
        return []
    placeholders = ",".join("?" * len(keys))
    sql = (
        f"SELECT * FROM user_preferences WHERE user_id = ? AND key IN ({placeholders}) "
        f"AND (source = 'explicit' OR confidence >= ?) "
        f"ORDER BY confidence DESC, updated_at DESC"
    )
    params: tuple = (user_id, *keys, min_confidence)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [
                UserPreference(
                    user_id=r["user_id"],
                    key=r["key"],
                    value=r["value"],
                    source=r["source"],
                    confidence=r["confidence"],
                    times_seen=r["times_seen"] if "times_seen" in r.keys() else 1,
                    created_at=r["created_at"],
                    updated_at=r["updated_at"] if "updated_at" in r.keys() else "",
                )
                for r in rows
            ]


async def delete_preference(user_id: str, key: str, value: str) -> bool:
    """Delete a specific preference. Returns True if deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM user_preferences WHERE user_id = ? AND key = ? AND value = ?",
            (user_id, key, value),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_inferred_preferences_by_keys(user_id: str, keys: list[str]) -> int:
    """Remove inferred preferences when user changes direction."""
    if not keys:
        return 0
    placeholders = ",".join("?" * len(keys))
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"DELETE FROM user_preferences WHERE user_id = ? AND source = 'inferred' "
            f"AND key IN ({placeholders})",
            (user_id, *keys),
        )
        await db.commit()
        return cursor.rowcount


# ── Legacy functions (backward compat) ───────────────────────────

async def save_memory(memory: UserMemory) -> None:
    """Upsert user memory (legacy)."""
    memory.updated_at = datetime.now(timezone.utc).isoformat()
    if not memory.created_at:
        memory.created_at = memory.updated_at

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_memory (
                user_id, resume_text, background, constraints,
                preferred_directions, last_profile_summary,
                last_matched_industries, last_plan_target,
                interview_count, avg_readiness_score, recurring_gaps,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                resume_text = excluded.resume_text,
                background = excluded.background,
                constraints = excluded.constraints,
                preferred_directions = excluded.preferred_directions,
                last_profile_summary = excluded.last_profile_summary,
                last_matched_industries = excluded.last_matched_industries,
                last_plan_target = excluded.last_plan_target,
                interview_count = excluded.interview_count,
                avg_readiness_score = excluded.avg_readiness_score,
                recurring_gaps = excluded.recurring_gaps,
                updated_at = excluded.updated_at
        """, (
            memory.user_id, memory.resume_text, memory.background,
            memory.constraints,
            json.dumps(memory.preferred_directions, ensure_ascii=False),
            memory.last_profile_summary,
            json.dumps(memory.last_matched_industries, ensure_ascii=False),
            memory.last_plan_target,
            memory.interview_count, memory.avg_readiness_score,
            json.dumps(memory.recurring_gaps, ensure_ascii=False),
            memory.created_at, memory.updated_at,
        ))
        await db.commit()


async def load_memory(user_id: str) -> UserMemory | None:
    """Load user memory (legacy). Returns None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_memory WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return UserMemory(
                user_id=row["user_id"],
                resume_text=row["resume_text"],
                background=row["background"],
                constraints=row["constraints"],
                preferred_directions=json.loads(row["preferred_directions"]),
                last_profile_summary=row["last_profile_summary"],
                last_matched_industries=json.loads(row["last_matched_industries"]),
                last_plan_target=row["last_plan_target"],
                interview_count=row["interview_count"],
                avg_readiness_score=row["avg_readiness_score"],
                recurring_gaps=json.loads(row["recurring_gaps"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )


async def save_analysis(record: AnalysisRecord) -> None:
    """Save a pipeline analysis record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO analysis_records
            (record_id, user_id, timestamp, user_input_json,
             pipeline_result_json, interview_report_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record.record_id, record.user_id, record.timestamp,
            record.user_input_json, record.pipeline_result_json,
            record.interview_report_json,
        ))
        await db.commit()


async def list_analyses(user_id: str, limit: int = 10) -> list[AnalysisRecord]:
    """List recent analysis records for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM analysis_records WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                AnalysisRecord(
                    record_id=r["record_id"],
                    user_id=r["user_id"],
                    timestamp=r["timestamp"],
                    user_input_json=r["user_input_json"],
                    pipeline_result_json=r["pipeline_result_json"],
                    interview_report_json=r["interview_report_json"],
                )
                for r in rows
            ]


async def list_legacy_user_ids_without_profile() -> list[str]:
    """User IDs with legacy user_memory row but no user_profiles row."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT um.user_id FROM user_memory um
            LEFT JOIN user_profiles up ON um.user_id = up.user_id
            WHERE up.user_id IS NULL
        """)
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
