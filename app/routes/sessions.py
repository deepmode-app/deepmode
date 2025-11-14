from datetime import datetime, date
from typing import List

from fastapi import APIRouter, HTTPException

from app.models.schemas import SessionCreate, SessionRead, SessionSummary

from app.database import create_session, list_sessions_db, get_session, end_session_db


router = APIRouter()

MAX_FREE_SESSIONS_PER_DAY = 3

# Helper: convert DB row -> SessionRead Pydantic model
def row_to_session_read(row) -> SessionRead:
    return SessionRead(
        id=row["id"],
        user_id=1,  # single user for now
        task=row["task"],
        category=row["category"],
        planned_duration_minutes=row["planned_duration_minutes"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        actual_duration_minutes=row["actual_duration_minutes"],
        discipline_score=row["discipline_score"],
    )


@router.get("/", response_model=List[SessionRead])
def list_sessions():
    """
    Return all sessions from the database (currently single-user).
    """
    rows = list_sessions_db()
    return [row_to_session_read(r) for r in rows]


@router.post("/", response_model=SessionRead)
def create_new_session(payload: SessionCreate):
    """
    Create a new deepwork session and store it in SQLite.
    Enforce a simple free-tier limit: max N sessions per day.
    """
    # --- FREE TIER DAILY LIMIT CHECK ---
    rows = list_sessions_db()
    today_str = date.today().isoformat()

    sessions_today = sum(
        1 for r in rows
        if r["start_time"] is not None and r["start_time"].startswith(today_str)
    )

    if sessions_today >= MAX_FREE_SESSIONS_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail="You’ve hit today’s focus limit — pros train daily. Upgrade to access unlimited Deepwork sessions and track your productivity like a professional with AI support."        )

    # --- CREATE SESSION ---
    start_time = datetime.utcnow().isoformat()

    row = create_session(
        task=payload.task,
        category=payload.category,
        planned_duration_minutes=payload.planned_duration_minutes,
        start_time=start_time,
    )

    return row_to_session_read(row)



@router.patch("/{session_id}/end", response_model=SessionRead)
def end_session(session_id: int):
    """
    End a session: compute actual duration and discipline_score,
    then update the row in SQLite.
    """
    row = get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.utcnow()
    start = datetime.fromisoformat(row["start_time"])
    diff = now - start
    actual_minutes = int(diff.total_seconds() // 60)

    planned = row["planned_duration_minutes"]
    discipline_score = 1 if actual_minutes >= planned else 0

    updated_row = end_session_db(
        session_id=session_id,
        end_time=now.isoformat(),
        actual_duration_minutes=actual_minutes,
        discipline_score=discipline_score,
    )

    return row_to_session_read(updated_row)


@router.get("/summary", response_model=SessionSummary)
def get_summary():
    """
    Return aggregate stats for the current (single) user:
    - minutes today
    - minutes all time
    - total sessions
    - completed sessions
    """
    rows = list_sessions_db()
    today_str = date.today().isoformat()

    today_minutes = 0
    all_time_minutes = 0
    total_sessions = len(rows)
    completed_sessions = 0

    for r in rows:
        mins = r["actual_duration_minutes"] or 0

        # Sum all-time minutes
        all_time_minutes += mins

        # Count completed sessions
        if r["end_time"] is not None:
            completed_sessions += 1

            # Check if completed today
            if r["end_time"].startswith(today_str):
                today_minutes += mins

    return SessionSummary(
        today_minutes=today_minutes,
        all_time_minutes=all_time_minutes,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
    )
