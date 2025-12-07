# app/jobs/email_jobs.py

from datetime import date, timedelta
from fastapi import APIRouter
from collections import defaultdict

from app.database import get_conn
from app.email_utils import (
    send_daily_streak_email,
    send_weekly_summary_email,
    send_minimal_weekly_summary_email,
    send_ai_weekly_summary_email,
    send_ai_daily_email,
)
from app.ai.weekly_reports import generate_ai_weekly_summary
from app.ai.daily_reports import generate_ai_daily_summary
from app.ai_config import AI_EMAIL_ENABLED, OPENAI_API_KEY


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

        # Get yesterday's stats for AI daily email
        # First get aggregate counts
        cur.execute(
            """
            SELECT 
                COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS total_mins,
                COUNT(*)::INT AS session_count,
                COUNT(CASE WHEN end_time IS NOT NULL AND status = 'completed' THEN 1 END)::INT AS completed,
                COUNT(CASE WHEN status = 'abandoned' THEN 1 END)::INT AS abandoned,
                COUNT(CASE WHEN status = 'completed_early' THEN 1 END)::INT AS stopped_early
            FROM sessions
            WHERE user_id = %s
              AND end_time::date = %s::date
              AND end_time IS NOT NULL
            """,
            (user_id, yesterday),
        )
        row_agg = cur.fetchone()
        minutes_yesterday = row_agg.get("total_mins", 0) if row_agg else 0
        sessions_yesterday = row_agg.get("session_count", 0) if row_agg else 0
        completed_yesterday = row_agg.get("completed", 0) if row_agg else 0
        abandoned_yesterday = row_agg.get("abandoned", 0) if row_agg else 0
        stopped_early_yesterday = row_agg.get("stopped_early", 0) if row_agg else 0
        
        # Get category breakdown
        cur.execute(
            """
            SELECT 
                category,
                COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
            FROM sessions
            WHERE user_id = %s
              AND end_time::date = %s::date
              AND end_time IS NOT NULL
              AND category IS NOT NULL
            GROUP BY category
            """,
            (user_id, yesterday),
        )
        category_rows = cur.fetchall()
        category_minutes = defaultdict(int)
        for row in category_rows:
            cat = row.get("category")
            mins = row.get("mins", 0) or 0
            if cat:
                category_minutes[cat] += mins
        
        # Get project breakdown
        cur.execute(
            """
            SELECT 
                project_name,
                COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
            FROM sessions
            WHERE user_id = %s
              AND end_time::date = %s::date
              AND end_time IS NOT NULL
              AND project_name IS NOT NULL
            GROUP BY project_name
            """,
            (user_id, yesterday),
        )
        project_rows = cur.fetchall()
        project_minutes = defaultdict(int)
        for row in project_rows:
            proj = row.get("project_name")
            mins = row.get("mins", 0) or 0
            if proj:
                project_minutes[proj] += mins
        
        # Get user profile data for AI
        cur.execute(
            """
            SELECT first_name, organization, timezone
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        user_row = cur.fetchone()
        user_profile = {
            "email": email,
            "first_name": user_row.get("first_name") if user_row else None,
            "organization": user_row.get("organization") if user_row else None,
        }
        
        # Build daily stats dict
        daily_stats = {
            "minutes_yesterday": minutes_yesterday,
            "sessions_yesterday": sessions_yesterday,
            "completed_yesterday": completed_yesterday,
            "abandoned_yesterday": abandoned_yesterday,
            "stopped_early_yesterday": stopped_early_yesterday,
            "top_categories": sorted(category_minutes.items(), key=lambda x: x[1], reverse=True),
            "top_projects": sorted(project_minutes.items(), key=lambda x: x[1], reverse=True),
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "timezone": user_row.get("timezone", "UTC") if user_row else "UTC",
        }

        try:
            # Try AI-enhanced daily email for Pro users
            if AI_EMAIL_ENABLED and OPENAI_API_KEY:
                ai_html = generate_ai_daily_summary(user_profile, daily_stats)
                if ai_html:
                    send_ai_daily_email(email, daily_stats, ai_html)
                    sent_count += 1
                else:
                    # Fallback to non-AI email
                    send_daily_streak_email(
                        email,
                        current_streak=current_streak,
                        longest_streak=longest_streak,
                        minutes_yesterday=minutes_yesterday,
                    )
                    sent_count += 1
            else:
                # AI disabled or no key - use non-AI email
                send_daily_streak_email(
                    email,
                    current_streak=current_streak,
                    longest_streak=longest_streak,
                    minutes_yesterday=minutes_yesterday,
                )
                sent_count += 1
        except Exception as e:
            print(f"[Jobs] Error sending daily email to {email}: {e}")
            # Try fallback
            try:
                send_daily_streak_email(
                    email,
                    current_streak=current_streak,
                    longest_streak=longest_streak,
                    minutes_yesterday=minutes_yesterday,
                )
                sent_count += 1
            except Exception as e2:
                print(f"[Jobs] Error sending fallback daily email to {email}: {e2}")

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
            # Pro users get AI-enhanced weekly summary (with fallback)
            # Aggregate stats for this week
            # First get aggregate counts
            cur.execute(
                """
                SELECT 
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS total_mins,
                    COUNT(*)::INT AS session_count,
                    COUNT(CASE WHEN end_time IS NOT NULL AND status = 'completed' THEN 1 END)::INT AS completed,
                    COUNT(CASE WHEN status = 'abandoned' THEN 1 END)::INT AS abandoned,
                    COUNT(CASE WHEN status = 'completed_early' THEN 1 END)::INT AS stopped_early
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                """,
                (user_id, start_of_this_week, today),
            )
            row_agg = cur.fetchone()
            minutes_this_week = row_agg.get("total_mins", 0) if row_agg else 0
            total_sessions_this_week = row_agg.get("session_count", 0) if row_agg else 0
            completed_sessions_this_week = row_agg.get("completed", 0) if row_agg else 0
            abandoned_sessions_this_week = row_agg.get("abandoned", 0) if row_agg else 0
            stopped_early_sessions_this_week = row_agg.get("stopped_early", 0) if row_agg else 0
            
            # Get category breakdown
            cur.execute(
                """
                SELECT 
                    category,
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                  AND category IS NOT NULL
                GROUP BY category
                """,
                (user_id, start_of_this_week, today),
            )
            category_rows = cur.fetchall()
            category_minutes = defaultdict(int)
            for row in category_rows:
                cat = row.get("category")
                mins = row.get("mins", 0) or 0
                if cat:
                    category_minutes[cat] += mins
            
            # Get project breakdown
            cur.execute(
                """
                SELECT 
                    project_name,
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                  AND project_name IS NOT NULL
                GROUP BY project_name
                """,
                (user_id, start_of_this_week, today),
            )
            project_rows = cur.fetchall()
            project_minutes = defaultdict(int)
            for row in project_rows:
                proj = row.get("project_name")
                mins = row.get("mins", 0) or 0
                if proj:
                    project_minutes[proj] += mins
            
            # Get weekday breakdown
            cur.execute(
                """
                SELECT 
                    EXTRACT(DOW FROM end_time)::INT AS weekday,
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                GROUP BY EXTRACT(DOW FROM end_time)
                """,
                (user_id, start_of_this_week, today),
            )
            weekday_rows = cur.fetchall()
            weekday_minutes = defaultdict(int)
            weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            for row in weekday_rows:
                weekday_num = row.get("weekday")
                mins = row.get("mins", 0) or 0
                if weekday_num is not None:
                    # PostgreSQL DOW: 0=Sunday, 1=Monday, ... 6=Saturday
                    # Convert to Mon=0, Tue=1, ... Sun=6
                    weekday_idx = (weekday_num + 6) % 7
                    weekday_minutes[weekday_names[weekday_idx]] += mins

            # Minutes last week
            cur.execute(
                """
                SELECT COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
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
                  COUNT(CASE WHEN end_time IS NOT NULL THEN 1 END)::INT AS completed_sessions
                FROM sessions
                WHERE user_id = %s
                """,
                (user_id,),
            )
            r_stats = cur.fetchone()
            total_sessions = r_stats["total_sessions"] if r_stats else 0
            completed_sessions = r_stats["completed_sessions"] if r_stats else 0

            # Get user profile data for AI
            cur.execute(
                """
                SELECT first_name, organization, timezone
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            user_row = cur.fetchone()
            user_profile = {
                "email": email,
                "first_name": user_row.get("first_name") if user_row else None,
                "organization": user_row.get("organization") if user_row else None,
            }

            # Build stats dict for AI
            stats = {
                "minutes_this_week": minutes_this_week,
                "minutes_last_week": minutes_last_week,
                "total_sessions": total_sessions_this_week,
                "completed_sessions": completed_sessions_this_week,
                "abandoned_sessions": abandoned_sessions_this_week,
                "stopped_early_sessions": stopped_early_sessions_this_week,
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "by_category": dict(category_minutes),
                "by_project": dict(project_minutes),
                "by_weekday": dict(weekday_minutes),
                "timezone": user_row.get("timezone", "UTC") if user_row else "UTC",
            }

            try:
                # Try AI-enhanced weekly email for Pro users
                if AI_EMAIL_ENABLED and OPENAI_API_KEY:
                    ai_html = generate_ai_weekly_summary(user_profile, stats)
                    if ai_html:
                        send_ai_weekly_summary_email(email, stats, ai_html)
                        sent_count += 1
                    else:
                        # Fallback to non-AI email
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
                else:
                    # AI disabled or no key - use non-AI email
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
                print(f"[Jobs] Error sending weekly email to {email}: {e}")
                # Try fallback
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
                except Exception as e2:
                    print(f"[Jobs] Error sending fallback weekly email to {email}: {e2}")
        else:
            # Free users get enhanced weekly summary (no AI)
            # Get comprehensive stats for last 7 days
            cur.execute(
                """
                SELECT 
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS total_mins,
                    COUNT(*)::INT AS session_count,
                    COUNT(CASE WHEN end_time IS NOT NULL AND (discipline_score = 1 OR status = 'completed') THEN 1 END)::INT AS completed,
                    COUNT(DISTINCT end_time::date)::INT AS days_worked
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                """,
                (user_id, start_of_this_week, today),
            )
            row_agg = cur.fetchone()
            minutes_this_week = row_agg.get("total_mins", 0) if row_agg else 0
            total_sessions = row_agg.get("session_count", 0) if row_agg else 0
            completed_sessions = row_agg.get("completed", 0) if row_agg else 0
            days_worked = row_agg.get("days_worked", 0) if row_agg else 0

            # Get top project
            cur.execute(
                """
                SELECT 
                    project_name,
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                  AND project_name IS NOT NULL
                  AND project_name != ''
                GROUP BY project_name
                ORDER BY mins DESC
                LIMIT 1
                """,
                (user_id, start_of_this_week, today),
            )
            top_project_row = cur.fetchone()
            top_project_name = top_project_row.get("project_name") if top_project_row else None
            top_project_minutes = top_project_row.get("mins", 0) if top_project_row else None

            # Get top category
            cur.execute(
                """
                SELECT 
                    category,
                    COALESCE(SUM(COALESCE(actual_duration_minutes, duration_seconds / 60, 0)), 0)::INT AS mins
                FROM sessions
                WHERE user_id = %s
                  AND end_time::date >= %s::date
                  AND end_time::date <= %s::date
                  AND end_time IS NOT NULL
                  AND category IS NOT NULL
                  AND category != ''
                GROUP BY category
                ORDER BY mins DESC
                LIMIT 1
                """,
                (user_id, start_of_this_week, today),
            )
            top_category_row = cur.fetchone()
            top_category_name = top_category_row.get("category") if top_category_row else None

            try:
                send_minimal_weekly_summary_email(
                    email,
                    minutes_this_week=minutes_this_week,
                    total_sessions=total_sessions,
                    completed_sessions=completed_sessions,
                    days_worked=days_worked,
                    current_streak=current_streak,
                    top_project_name=top_project_name,
                    top_project_minutes=top_project_minutes,
                    top_category_name=top_category_name,
                )
                sent_count += 1
            except Exception as e:
                print(f"[Jobs] Error sending minimal weekly summary to {email}: {e}")

    conn.close()
    return {"status": "ok", "sent": sent_count}
