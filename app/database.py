# app/database.py

import os
from pathlib import Path  # still useful if you ever want file logging, etc.

import psycopg2
from psycopg2.extras import RealDictCursor

# Single source of truth for DB URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Determine database backend
DB_BACKEND = "postgres" if DATABASE_URL else "sqlite"


def get_conn():
    """
    Return a new PostgreSQL connection using RealDictCursor so rows behave like dicts.
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in environment.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def get_db():
    """
    FastAPI dependency-style generator (if you use Depends(get_db)).
    Ensures connection is closed after the request.
    """
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """
    Initialize Postgres schema for Deepmode.

    - users: full auth + streak + email + Stripe subscription fields
    - sessions: tracking Deepmode blocks
    """
    conn = get_conn()
    cur = conn.cursor()

    # ---------- users table ----------
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_pro BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),

            -- Email verification
            is_verified BOOLEAN DEFAULT FALSE,
            verification_token TEXT,
            verification_expires_at TIMESTAMPTZ,

            -- Password reset
            reset_token UUID,
            reset_token_expires_at TIMESTAMPTZ,
            reset_password_token VARCHAR(255),
            reset_password_expires_at TIMESTAMPTZ,

            -- Activity / streaks
            last_active_date DATE,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,

            -- Email preferences
            weekly_email_enabled BOOLEAN DEFAULT TRUE,
            unsub_token TEXT UNIQUE,
            daily_email_enabled BOOLEAN NOT NULL DEFAULT FALSE,

            -- Stripe subscription linkage
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            stripe_subscription_status TEXT,
            stripe_price_id TEXT,
            stripe_cancel_at_period_end BOOLEAN DEFAULT FALSE
        );
        """
    )

    # ---------- sessions table ----------
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,

            task TEXT NOT NULL,
            category TEXT,
            planned_duration_minutes INTEGER NOT NULL,

            start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            end_time TIMESTAMPTZ,
            actual_duration_minutes INTEGER,
            discipline_score INTEGER,
            status TEXT DEFAULT 'running',
            duration_seconds INTEGER,

            project_name VARCHAR(255),
            notes TEXT
        );
        """
    )

    conn.commit()
    cur.close()
    conn.close()
