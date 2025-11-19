import sqlite3
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).resolve().parent / "deepwork.db"


def get_conn() -> sqlite3.Connection:
    """
    Return a SQLite connection with:
    - row_factory set to Row (so rows behave like dicts)
    - check_same_thread=False so FastAPI can use it across worker threads
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency that yields a SQLite connection
    and closes it after the request.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """
    Create sessions + users tables if they don't exist.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()

    # sessions table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task TEXT NOT NULL,
            category TEXT NOT NULL,
            planned_duration_minutes INTEGER NOT NULL,
            actual_duration_minutes INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT,
            discipline_score INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    # users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            stripe_customer_id TEXT,
            is_pro INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


# ---------- Session helper functions used by other routes (keep for later multi-user) ----------

def create_session(
    user_id: int,
    task: str,
    category: str,
    planned_duration_minutes: int,
    start_time: str,
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sessions (user_id, task, category, planned_duration_minutes, start_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, task, category, planned_duration_minutes, start_time),
    )
    session_id = cur.lastrowid
    conn.commit()
    row = cur.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    return row


def get_session(session_id: int, user_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    ).fetchone()
    conn.close()
    return row


def end_session_db(
    session_id: int,
    end_time: str,
    actual_duration_minutes: int,
    discipline_score: int,
):
    """
    Mark a session as ended and update duration + discipline score.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE sessions
        SET end_time = ?, actual_duration_minutes = ?, discipline_score = ?
        WHERE id = ?
        """,
        (end_time, actual_duration_minutes, discipline_score, session_id),
    )
    conn.commit()
    row = cur.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    return row


def list_sessions_db(user_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE user_id = ? ORDER BY start_time DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows
