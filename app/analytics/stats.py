# app/analytics/stats.py

from datetime import date, timedelta, datetime, timezone as dt_timezone
from collections import defaultdict
from typing import Dict, List, Optional

try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False

from app.database import get_conn


def get_user_timezone(user_id: int) -> Optional[str]:
    """Get user's timezone from database, return None if not set."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT timezone FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row.get("timezone") if row else None


def get_today_in_timezone(tz_name: Optional[str] = None) -> date:
    """Get today's date in the user's timezone, or UTC if not set."""
    if tz_name and HAS_PYTZ:
        try:
            tz = pytz.timezone(tz_name)
            return datetime.now(tz).date()
        except:
            pass
    return date.today()


def compute_work_tracker_stats(user_id: int, days: int = 7, timezone_name: Optional[str] = None) -> Dict:
    """
    Compute comprehensive work tracker stats for a user over a time window.
    
    Returns a dict with:
    - total_minutes
    - sessions_completed
    - sessions_abandoned
    - sessions_stopped_early
    - days_worked
    - best_day
    - weakest_day
    - by_weekday (list of dicts)
    - projects (list of dicts)
    - categories (list of dicts)
    - context_switch_index
    - days (list of dicts with daily breakdown for last 7 days)
    """
    today = get_today_in_timezone(timezone_name)
    start_date = today - timedelta(days=days - 1)
    
    # Build list of all 7 days
    all_days = []
    weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i in range(days):
        day_date = start_date + timedelta(days=i)
        day_label = weekday_names[day_date.weekday()]
        all_days.append({
            "date": day_date.isoformat(),
            "label": day_label,
            "minutes": 0,
            "sessions_completed": 0,
            "sessions_abandoned": 0,
        })
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all sessions in the window
    # Note: We query with a wider range to account for timezone differences
    # Then filter by date in the user's timezone in Python
    query_start = start_date - timedelta(days=1)  # Buffer for timezone
    query_end = today + timedelta(days=1)
    
    cur.execute(
        """
        SELECT 
            end_time,
            actual_duration_minutes,
            duration_seconds,
            status,
            discipline_score,
            project_name,
            category,
            start_time
        FROM sessions
        WHERE user_id = %s
          AND end_time IS NOT NULL
          AND end_time >= %s
          AND end_time <= %s
        ORDER BY end_time
        """,
        (user_id, query_start, query_end),
    )
    rows = cur.fetchall()
    
    # Convert timestamps to user timezone if needed
    tz = None
    if timezone_name and HAS_PYTZ:
        try:
            tz = pytz.timezone(timezone_name)
        except:
            pass
    
    # Initialize aggregators
    total_minutes = 0
    sessions_completed = 0
    sessions_abandoned = 0
    sessions_stopped_early = 0
    days_with_work = set()
    day_minutes = defaultdict(int)
    project_data = defaultdict(lambda: {"minutes": 0, "sessions": 0})
    category_data = defaultdict(lambda: {"minutes": 0, "sessions": 0})
    weekday_minutes = defaultdict(int)
    weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    for row in rows:
        # Extract status and discipline first (before any continue statements)
        status = row.get("status", "")
        discipline = row.get("discipline_score", 0)
        
        # Calculate minutes (prefer actual_duration_minutes, fall back to duration_seconds/60)
        mins = row.get("actual_duration_minutes") or 0
        if mins == 0 and row.get("duration_seconds"):
            mins = row.get("duration_seconds", 0) / 60
        
        total_minutes += mins
        
        # Status tracking (do this before timezone conversion)
        if discipline == 1 or status == "completed":
            sessions_completed += 1
        elif status == "abandoned":
            sessions_abandoned += 1
        elif status == "completed_early":
            sessions_stopped_early += 1
        
        # Track day
        end_time = row.get("end_time")
        if end_time:
            # Convert to user timezone if needed
            if tz and hasattr(end_time, 'astimezone'):
                # Already timezone-aware
                if end_time.tzinfo is None:
                    # Assume UTC if naive
                    if HAS_PYTZ:
                        end_time = pytz.utc.localize(end_time)
                    else:
                        end_time = end_time.replace(tzinfo=dt_timezone.utc)
                work_datetime = end_time.astimezone(tz)
                work_date = work_datetime.date()
            elif isinstance(end_time, str):
                try:
                    dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    if tz:
                        if dt.tzinfo is None:
                            if HAS_PYTZ:
                                dt = pytz.utc.localize(dt)
                            else:
                                dt = dt.replace(tzinfo=dt_timezone.utc)
                        work_datetime = dt.astimezone(tz)
                        work_date = work_datetime.date()
                    else:
                        work_date = dt.date()
                except:
                    work_date = date.fromisoformat(end_time.split('T')[0])
            elif hasattr(end_time, 'date'):
                work_date = end_time.date()
            else:
                continue
            
            # Only count if within our window
            if work_date < start_date or work_date > today:
                continue
            
            days_with_work.add(work_date)
            day_minutes[work_date] += mins
            
            # Update daily breakdown
            day_key = work_date.isoformat()
            for day_entry in all_days:
                if day_entry["date"] == day_key:
                    day_entry["minutes"] += int(mins)
                    if discipline == 1 or status == "completed":
                        day_entry["sessions_completed"] += 1
                    elif status == "abandoned":
                        day_entry["sessions_abandoned"] += 1
                    break
            
            # Weekday (Python date.weekday() returns Monday=0)
            weekday_num = work_date.weekday()
            weekday_minutes[weekday_names[weekday_num]] += mins
        
        # Project tracking
        project = row.get("project_name")
        if project and project.strip():
            project_data[project]["minutes"] += mins
            project_data[project]["sessions"] += 1
        
        # Category tracking
        category = row.get("category")
        if category and category.strip():
            category_data[category]["minutes"] += mins
            category_data[category]["sessions"] += 1
    
    # Find best and weakest days
    best_day = None
    weakest_day = None
    if day_minutes:
        sorted_days = sorted(day_minutes.items(), key=lambda x: x[1], reverse=True)
        if sorted_days:
            best_date, best_mins = sorted_days[0]
            worst_date, worst_mins = sorted_days[-1]
            
            # Get weekday name
            best_weekday = weekday_names[best_date.weekday()]
            worst_weekday = weekday_names[worst_date.weekday()]
            
            best_day = {"weekday": best_weekday, "minutes": int(best_mins)}
            weakest_day = {"weekday": worst_weekday, "minutes": int(worst_mins)}
    
    # Format weekday breakdown
    by_weekday = [
        {"weekday": day, "minutes": int(weekday_minutes[day])}
        for day in weekday_names
    ]
    
    # Format projects (sorted by minutes desc)
    projects = [
        {
            "project_name": proj,
            "minutes": int(data["minutes"]),
            "sessions": data["sessions"]
        }
        for proj, data in sorted(project_data.items(), key=lambda x: x[1]["minutes"], reverse=True)
    ]
    
    # Format categories (sorted by minutes desc)
    categories = [
        {
            "category": cat,
            "minutes": int(data["minutes"]),
            "sessions": data["sessions"]
        }
        for cat, data in sorted(category_data.items(), key=lambda x: x[1]["minutes"], reverse=True)
    ]
    
    # Compute context switching index
    total_sessions = sessions_completed + sessions_abandoned + sessions_stopped_early
    distinct_projects = len([p for p in projects if p["minutes"] > 0])
    context_switch_index = None
    if total_sessions > 0 and distinct_projects > 0:
        context_switch_index = round(distinct_projects / total_sessions, 2)
    
    conn.close()
    
    # Limit projects and categories to top 3
    top_projects = projects[:3]
    top_categories = categories[:3]
    
    return {
        "total_minutes": int(total_minutes),
        "sessions_completed": sessions_completed,
        "sessions_abandoned": sessions_abandoned,
        "sessions_stopped_early": sessions_stopped_early,
        "days_worked": len(days_with_work),
        "best_day": best_day,
        "weakest_day": weakest_day,
        "by_weekday": by_weekday,
        "projects": top_projects,
        "categories": top_categories,
        "context_switch_index": context_switch_index,
        "days": all_days,
    }

