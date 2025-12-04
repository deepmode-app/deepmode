from datetime import datetime, date, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Depends

from app.models.schemas import (
    SessionCreate,
    SessionRead,
    SessionSummary,
    SessionUpdate,
)
from app.database import get_conn
from app.routes.auth import get_current_user  # uses the JWT to load user from DB

router = APIRouter(tags=["sessions"])

# ---------- FREE TIER LIMITS ----------

# How many focus blocks a free user can start per day
MAX_FREE_SESSIONS_PER_DAY = 3

# Which durations (in minutes) are allowed on the free plan
FREE_ALLOWED_DURATIONS_MINUTES = {5, 25}


def row_to_session_read(row) -> SessionRead:
    """
    Convert a DB row into a SessionRead Pydantic model.
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
        status=row.get("status"),
        duration_seconds=row.get("duration_seconds"),
        project_name=row.get("project_name"),
        notes=row.get("notes"),
    )


def derive_status_and_discipline(planned: Optional[int], actual_minutes: int) -> tuple[str, int]:
    """
    Given planned duration (minutes) and actual work duration (minutes),
    return (status, discipline_score).

    Status is one of: "abandoned", "stopped_early", "completed_early", "completed".
    Discipline_score is 0 or 1.

    Rules (ratio-based for ALL durations, including 5-minute blocks):
    - ratio = actual_minutes / planned_minutes (0.0 if planned <= 0)
    - ratio >= 1.0 → "completed", discipline_score = 1
    - 0.5 <= ratio < 1.0 → "completed_early", discipline_score = 1
    - 0.25 <= ratio < 0.5 → "stopped_early", discipline_score = 0
    - ratio < 0.25 → "abandoned", discipline_score = 0

    - If planned is None:
      * actual >= 5 → "completed", discipline_score = 1
      * actual < 5 → "abandoned", discipline_score = 0
    """
    # Handle None planned duration
    if planned is None:
        if actual_minutes >= 5:
            return ("completed", 1)
        else:
            return ("abandoned", 0)

    # Ratio-based logic for all durations (5, 25, 50, 90 minutes)
    if planned > 0:
        ratio = actual_minutes / planned
    else:
        ratio = 0.0

    if ratio >= 1.0:
        return ("completed", 1)
    elif ratio >= 0.5:
        return ("completed_early", 1)
    elif ratio >= 0.25:
        return ("stopped_early", 0)
    else:
        return ("abandoned", 0)


def auto_close_expired_sessions_for_user(user_id: int) -> None:
    """
    Auto-close any 'running' sessions that are clearly stale.
    Currently: if a session has been 'running' for more than 6 hours,
    we mark it as 'auto_closed' and compute duration.
    """
    conn = get_conn()
    cur = conn.cursor()

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


def update_streak_for_user(user_id: int):
    """
    Called whenever a user successfully completes ANY session.
    Updates: last_active_date, current_streak, longest_streak.
    """
    conn = get_conn()
    cur = conn.cursor()

    # Load streak fields
    cur.execute(
        """
        SELECT last_active_date, current_streak, longest_streak
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        return

    last_active_date = row["last_active_date"]
    current = row["current_streak"] or 0
    longest = row["longest_streak"] or 0

    today = datetime.utcnow().date()

    # FIRST SESSION EVER
    if last_active_date is None:
        new_streak = 1
        longest = max(longest, new_streak)

        cur.execute(
            """
            UPDATE users
            SET last_active_date = %s,
                current_streak = %s,
                longest_streak = %s
            WHERE id = %s
            """,
            (today, new_streak, longest, user_id),
        )
        conn.commit()
        conn.close()
        return

    # SAME DAY — Don't increment streak twice
    if last_active_date == today:
        conn.close()
        return

    # WORKED YESTERDAY → streak continues
    if last_active_date == (today - timedelta(days=1)):
        new_streak = current + 1
        longest = max(longest, new_streak)
    else:
        # Streak broken
        new_streak = 1

    cur.execute(
        """
        UPDATE users
        SET last_active_date = %s,
            current_streak = %s,
            longest_streak = %s
        WHERE id = %s
        """,
        (today, new_streak, longest, user_id),
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

    # ---- FREE TIER LIMITS ----
    if not is_pro:
        # 1) Daily session cap
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
                detail={
                    "code": "FREE_LIMIT_REACHED",
                    "message": (
                        "You’ve used all 3 free Deepmode focus blocks for today. "
                        "Upgrade to Pro for unlimited sessions and longer 50/90 minute blocks."
                    ),
                },
            )

        # 2) Duration restriction: free users only get 5m + 25m
        planned = payload.planned_duration_minutes
        if planned not in FREE_ALLOWED_DURATIONS_MINUTES:
            conn.close()
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PRO_DURATION_ONLY",
                    "message": (
                        "50 and 90 minute focus blocks are part of Deepmode Pro. "
                        "Upgrade to unlock deeper, distraction-free work."
                    ),
                },
            )

    # ---- CREATE SESSION ----
    start_time = datetime.now(timezone.utc)

    cur.execute(
        """
        INSERT INTO sessions (
            user_id, task, category, planned_duration_minutes, start_time, status
        )
        VALUES (%s, %s, %s, %s, %s, 'running')
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
    - set status = 'abandoned', 'completed_early', or 'completed'
    - update streak if there was real work (>= 5 minutes)
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # Ownership check
    if row["user_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not your session")

    # If already has an end_time, just return the row (idempotent)
    if row["end_time"] is not None:
        conn.close()
        return row_to_session_read(row)

    now = datetime.now(timezone.utc)

    start = row["start_time"]
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    diff = now - start
    actual_minutes = max(1, int(diff.total_seconds() // 60))
    planned = row["planned_duration_minutes"]

    # Derive status and discipline using the standardized helper
    status_val, discipline_score = derive_status_and_discipline(planned, actual_minutes)

    cur.execute(
        """
        UPDATE sessions
        SET end_time = %s,
            actual_duration_minutes = %s,
            discipline_score = %s,
            status = %s
        WHERE id = %s
        """,
        (
            now,
            actual_minutes,
            discipline_score,
            status_val,
            session_id,
        ),
    )

    # Fetch updated row
    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    updated_row = cur.fetchone()

    conn.commit()
    conn.close()

    # 🔥 Update streak only if this block counts as a success
    if discipline_score == 1:
        try:
            update_streak_for_user(user_id)
        except Exception as e:
            print(f"[Deepmode] Error updating streak for user {user_id}: {e}")

    return row_to_session_read(updated_row)


@router.get("/active", response_model=Optional[SessionRead])
def get_active_session(current_user: dict = Depends(get_current_user)):
    """
    Get the latest active (no end_time) session for the current user.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
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
    - completed sessions (any with end_time != NULL)
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
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
            end_date = r["end_time"]
            if isinstance(end_date, datetime):
                end_date = end_date.date()
            elif isinstance(end_date, str):
                end_date = datetime.fromisoformat(
                    end_date.replace("Z", "+00:00")
                ).date()
            if end_date == today:
                today_minutes += mins

    return SessionSummary(
        today_minutes=today_minutes,
        all_time_minutes=all_time_minutes,
        total_sessions=total_sessions,
        completed_sessions=completed_sessions,
    )


@router.patch("/{session_id}", response_model=SessionRead)
def update_session(
    session_id: int,
    payload: SessionUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Partial update of a session (task, category, project_name, notes).
    Only fields provided in the body will be updated.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    # Load existing
    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    if row["user_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not your session")

    update_data = payload.dict(exclude_unset=True)
    if not update_data:
        conn.close()
        return row_to_session_read(row)

    set_clauses = []
    values = []

    mapping = {
        "task": "task",
        "category": "category",
        "project_name": "project_name",
        "notes": "notes",
    }

    for field, column in mapping.items():
        if field in update_data:
            set_clauses.append(f"{column} = %s")
            values.append(update_data[field])

    if not set_clauses:
        conn.close()
        return row_to_session_read(row)

    values.append(session_id)

    cur.execute(
        f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = %s",
        values,
    )

    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    updated_row = cur.fetchone()

    conn.commit()
    conn.close()

    return row_to_session_read(updated_row)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a session owned by the current user.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    if row["user_id"] != user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not your session")

    cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    conn.commit()
    conn.close()

    return
