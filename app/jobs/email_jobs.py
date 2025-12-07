# app/jobs/email_jobs.py

from datetime import date, timedelta
from fastapi import APIRouter

from app.database import get_conn
from app.email_utils import send_daily_streak_email, send_weekly_summary_email, send_minimal_weekly_summary_email, send_email_html


# This is what main.py imports as jobs_router
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/daily-streak-digest")
def run_daily_streak_digest():
    """
    Send daily 'don't break the chain' emails.

    Logic:
    - Only users with daily_email_enabled = TRUE
    - Only if they have a running streak (current_streak > 0)
    - Only if they have NOT logged any minutes TODAY (nudge to start)
    - Uses yesterday's minutes for context
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    conn = get_conn()
    cur = conn.cursor()

    # 1) Load candidates - PRO USERS ONLY (verification gating removed)
    cur.execute(
        """
        SELECT id, email, current_streak, longest_streak, last_active_date
        FROM users
        WHERE daily_email_enabled = TRUE
          AND is_pro = TRUE
          AND current_streak IS NOT NULL
          AND current_streak > 0
        """
    )
    users = cur.fetchall()

    sent_count = 0

    for u in users:
        user_id = u["id"]
        email = u["email"]
        current_streak = u["current_streak"] or 0
        longest_streak = u["longest_streak"] or 0
        last_active = u["last_active_date"]

        # If they already worked today, don't nag.
        if last_active == today:
            continue

        # Get yesterday's minutes for context
        cur.execute(
            """
            SELECT COALESCE(SUM(actual_duration_minutes), 0)::INT AS mins
            FROM sessions
            WHERE user_id = %s
              AND end_time::date = %s::date
            """,
            (user_id, yesterday),
        )
        row = cur.fetchone()
        minutes_yesterday = row["mins"] if row else 0

        try:
            send_daily_streak_email(
                email,
                current_streak=current_streak,
                longest_streak=longest_streak,
                minutes_yesterday=minutes_yesterday,
            )
            sent_count += 1
        except Exception as e:
            print(f"[Jobs] Error sending daily streak email to {email}: {e}")

    conn.close()
    return {"status": "ok", "sent": sent_count}


@router.post("/weekly-summary-digest")
def run_weekly_summary_digest():
    """
    Send weekly summary emails.

    Logic:
    - Only users with weekly_email_enabled = TRUE
    - Computes minutes for current week and previous week (Mon–Sun)
    """
    today = date.today()
    weekday = today.weekday()  # Monday=0
    start_of_this_week = today - timedelta(days=weekday)
    start_of_last_week = start_of_this_week - timedelta(days=7)
    end_of_last_week = start_of_this_week - timedelta(days=1)

    conn = get_conn()
    cur = conn.cursor()

    # 1) Load candidates (verification gating removed)
    cur.execute(
        """
        SELECT id, email, current_streak, longest_streak, is_pro
        FROM users
        WHERE weekly_email_enabled = TRUE
        """
    )
    users = cur.fetchall()

    sent_count = 0

    for u in users:
        user_id = u["id"]
        email = u["email"]
        current_streak = u["current_streak"] or 0
        longest_streak = u["longest_streak"] or 0
        is_pro = u["is_pro"]

        if is_pro:
            # Pro users get full weekly summary
            # Minutes this week
            cur.execute(
                """
                SELECT COALESCE(SUM(actual_duration_minutes), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                """,
                (user_id, start_of_this_week, today),
            )
            r_this = cur.fetchone()
            minutes_this_week = r_this["mins"] if r_this else 0

            # Minutes last week
            cur.execute(
                """
                SELECT COALESCE(SUM(actual_duration_minutes), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                """,
                (user_id, start_of_last_week, end_of_last_week),
            )
            r_last = cur.fetchone()
            minutes_last_week = r_last["mins"] if r_last else 0

            # Total / completed sessions all-time
            cur.execute(
                """
                SELECT
                  COUNT(*)::INT AS total_sessions,
                  COUNT(end_time)::INT AS completed_sessions
                FROM sessions
                WHERE user_id = %s
                """,
                (user_id,),
            )
            r_stats = cur.fetchone()
            total_sessions = r_stats["total_sessions"] if r_stats else 0
            completed_sessions = r_stats["completed_sessions"] if r_stats else 0

            try:
                send_weekly_summary_email(
                    email,
                    minutes_this_week=minutes_this_week,
                    minutes_last_week=minutes_last_week,
                    total_sessions=total_sessions,
                    completed_sessions=completed_sessions,
                    current_streak=current_streak,
                    longest_streak=longest_streak,
                )
                sent_count += 1
            except Exception as e:
                print(f"[Jobs] Error sending weekly summary to {email}: {e}")
        else:
            # Free users get minimal weekly summary
            # Count days worked this week
            cur.execute(
                """
                SELECT COUNT(DISTINCT end_time::date)::INT AS days_worked
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                """,
                (user_id, start_of_this_week, today),
            )
            r_days = cur.fetchone()
            days_worked = r_days["days_worked"] if r_days else 0

            try:
                send_minimal_weekly_summary_email(
                    email,
                    days_worked=days_worked,
                    current_streak=current_streak,
                )
                sent_count += 1
            except Exception as e:
                print(f"[Jobs] Error sending minimal weekly summary to {email}: {e}")

    conn.close()
    return {"status": "ok", "sent": sent_count}
