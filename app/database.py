import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "deepwork.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            category TEXT NOT NULL,
            planned_duration_minutes INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            actual_duration_minutes INTEGER,
            discipline_score INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def create_session(task: str, category: str, planned_duration_minutes: int, start_time: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sessions (task, category, planned_duration_minutes, start_time)
        VALUES (?, ?, ?, ?)
        """,
        (task, category, planned_duration_minutes, start_time),
    )
    session_id = cur.lastrowid
    conn.commit()
    row = cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return row


def get_session(session_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return row


def end_session_db(session_id: int, end_time: str, actual_duration_minutes: int, discipline_score: int):
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
    row = cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return row


def list_sessions_db():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows
