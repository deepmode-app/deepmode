from datetime import datetime, date, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Depends

from app.models.schemas import SessionCreate, SessionRead, SessionSummary
from app.database import get_conn
from app.routes.auth import get_current_user  # uses the JWT to load user from DB

router = APIRouter(tags=["sessions"])


# Free tier: per-user limit
MAX_FREE_SESSIONS_PER_DAY = 3  # tweak later if you want


def row_to_session_read(row) -> SessionRead:
    """
    Convert a SQLite row into a SessionRead Pydantic model.
    """
    return SessionRead(
        id=row["id"],
        user_id=row["user_id"],
        task=row["task"],
        category=row["category"],
        planned_duration_minutes=row["planned_duration_minutes"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        actual_duration_minutes=row["actual_duration_minutes"],
        discipline_score=row["discipline_score"],
    )


from datetime import datetime, timedelta

from app.database import get_conn

def auto_close_expired_sessions_for_user(user_id: int) -> None:
    """
    Auto-close any 'running' sessions that are clearly stale
    (e.g. user closed laptop, browser died, etc).

    For now: if a session has been 'running' for more than 6 hours,
    we mark it as 'auto_closed' and compute duration.
    """
    conn = get_conn()
    cur = conn.cursor()

    # Postgres-friendly query with %s placeholder
    cur.execute(
        """
        UPDATE sessions
        SET
            end_time = NOW(),
            duration_seconds = EXTRACT(EPOCH FROM (NOW() - start_time))::INT,
            status = 'auto_closed'
        WHERE user_id = %s
          AND status = 'running'
          AND end_time IS NULL
          AND start_time < NOW() - INTERVAL '6 hours';
        """,
        (user_id,),
    )

    conn.commit()
    conn.close()



@router.get("/", response_model=List[SessionRead])
def list_sessions(current_user: dict = Depends(get_current_user)):
    """
    Return all sessions for the logged-in user, most recent first.
    """
    user_id = current_user["id"]

    # Auto-close any expired sessions for this user
    auto_close_expired_sessions_for_user(user_id)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM sessions
        WHERE user_id = %s
        ORDER BY start_time DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    return [row_to_session_read(r) for r in rows]


@router.post("/", response_model=SessionRead)
def create_new_session(
    payload: SessionCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    is_pro = bool(current_user["is_pro"])

    conn = get_conn()
    cur = conn.cursor()

    # ---- FREE TIER LIMIT ----
    if not is_pro:
        
        today_str = date.today().isoformat()

        cur.execute(
            """
            SELECT COUNT(*)::INT AS count_today
            FROM sessions
            WHERE user_id = %s
            AND start_time::date = %s::date
            """,
            (user_id, today_str),
        )
        row = cur.fetchone()
        count_today = row["count_today"] if row else 0

        if count_today >= MAX_FREE_SESSIONS_PER_DAY:
            conn.close()
            raise HTTPException(
                status_code=403,
                detail="You’ve used today’s free focus blocks. Deepmode Pro unlocks unlimited sessions."
            )

    # ---- CREATE SESSION ----
    start_time = datetime.now(timezone.utc)

    cur.execute(
        """
        INSERT INTO sessions (
            user_id, task, category, planned_duration_minutes, start_time
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            user_id,
            payload.task,
            payload.category,
            payload.planned_duration_minutes,
            start_time,
        ),
    )

    row = cur.fetchone()
    session_id = row["id"]

    # Fetch full row
    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    new_row = cur.fetchone()

    conn.commit()
    conn.close()

    return row_to_session_read(new_row)



@router.patch("/{session_id}/end", response_model=SessionRead)
def end_session(
    session_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    End a session for the current user:
    - compute actual duration
    - compute discipline_score
    - update the row
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # Ownership check – don’t let one user end another user's session
    if row["user_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not your session")

    now = datetime.now(timezone.utc)
    # row["start_time"] is already a timezone-aware datetime from PostgreSQL
    start = row["start_time"]
    # Ensure start is timezone-aware (in case it's naive, make it UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    diff = now - start
    actual_minutes = int(diff.total_seconds() // 60)

    planned = row["planned_duration_minutes"]
    discipline_score = 1 if actual_minutes >= planned else 0

    cur.execute(
        """
        UPDATE sessions
        SET end_time = %s, actual_duration_minutes = %s, discipline_score = %s
        WHERE id = %s
        """,
        (
            now,  # Pass datetime object directly - psycopg2 handles TIMESTAMPTZ conversion
            actual_minutes,
            discipline_score,
            session_id,
        ),
    )

    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    updated_row = cur.fetchone()
    conn.commit()
    conn.close()

    return row_to_session_read(updated_row)


@router.get("/active", response_model=Optional[SessionRead])
def get_active_session(current_user: dict = Depends(get_current_user)):
    """
    Get the latest active (no end_time) session for the current user.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT *
        FROM sessions
        WHERE user_id = %s
          AND end_time IS NULL
        ORDER BY start_time DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        return row_to_session_read(row)
    return None


@router.get("/summary", response_model=SessionSummary)
def get_summary(current_user: dict = Depends(get_current_user)):
    """
    Aggregate stats for the current user:
    - minutes today
    - minutes all time
    - total sessions
    - completed sessions
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT * FROM sessions WHERE user_id = %s",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()

    today = date.today()

    today_minutes = 0
    all_time_minutes = 0
    total_sessions = len(rows)
    completed_sessions = 0

    for r in rows:
        mins = r["actual_duration_minutes"] or 0
        all_time_minutes += mins

        if r["end_time"] is not None:
            completed_sessions += 1
            # Handle both datetime objects and strings for compatibility
            end_date = r["end_time"]
            if isinstance(end_date, datetime):
                end_date = end_date.date()
            elif isinstance(end_date, str):
                # If it's a string, parse it
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00')).date()
            if end_date == today:
                today_minutes += mins

    return SessionSummary(
        today_minutes=today_minutes,
        all_time_minutes=all_time_minutes,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
    )
