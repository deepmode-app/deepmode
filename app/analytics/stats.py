# app/analytics/stats.py

from datetime import date, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

from app.database import get_conn


def compute_work_tracker_stats(user_id: int, days: int = 7) -> Dict:
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
    """
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all sessions in the window
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
          AND end_time::date >= %s::date
          AND end_time::date <= %s::date
        ORDER BY end_time
        """,
        (user_id, start_date, today),
    )
    rows = cur.fetchall()
    
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
        # Calculate minutes (prefer actual_duration_minutes, fall back to duration_seconds/60)
        mins = row.get("actual_duration_minutes") or 0
        if mins == 0 and row.get("duration_seconds"):
            mins = row.get("duration_seconds", 0) / 60
        
        total_minutes += mins
        
        # Track day
        end_date = row.get("end_time")
        if end_date:
            # Handle datetime objects
            if hasattr(end_date, 'date'):
                work_date = end_date.date()
            elif isinstance(end_date, str):
                from datetime import datetime
                try:
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    work_date = end_date.date()
                except:
                    # Fallback: try parsing as date string
                    work_date = date.fromisoformat(end_date.split('T')[0])
            else:
                work_date = end_date
            
            days_with_work.add(work_date)
            day_minutes[work_date] += mins
            
            # Weekday (Python date.weekday() returns Monday=0)
            weekday_num = work_date.weekday()
            weekday_minutes[weekday_names[weekday_num]] += mins
        
        # Status tracking
        status = row.get("status", "")
        discipline = row.get("discipline_score", 0)
        
        if discipline == 1 or status == "completed":
            sessions_completed += 1
        elif status == "abandoned":
            sessions_abandoned += 1
        elif status == "completed_early":
            sessions_stopped_early += 1
        
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
    
    return {
        "total_minutes": int(total_minutes),
        "sessions_completed": sessions_completed,
        "sessions_abandoned": sessions_abandoned,
        "sessions_stopped_early": sessions_stopped_early,
        "days_worked": len(days_with_work),
        "best_day": best_day,
        "weakest_day": weakest_day,
        "by_weekday": by_weekday,
        "projects": projects,
        "categories": categories,
        "context_switch_index": context_switch_index,
    }

