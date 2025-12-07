# app/ai/weekly_reports.py

import requests
import json

from app.ai_config import (
    OPENAI_API_KEY,
    AI_EMAIL_ENABLED,
    OPENAI_API_URL,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS_WEEKLY,
)


def generate_ai_weekly_summary(user, stats: dict) -> str:
    """
    Returns an HTML snippet (string) with the AI-generated narrative for the weekly report.
    On any error, returns empty string, and caller will fall back to non-AI email.
    """
    if not AI_EMAIL_ENABLED or not OPENAI_API_KEY:
        return ""

    try:
        # Build system prompt
        system_prompt = """You are Deepmode, a brutally honest but supportive focus coach.
You analyze a user's deep work stats for the last 7 days and write a concise, structured weekly report.
Tone: calm, confident, professional, no fluff, no emojis.
You speak directly to "you", not "the user"."""

        # Build user content with stats
        user_content = f"""Here are this user's weekly focus stats:

- Minutes this week: {stats.get('minutes_this_week', 0)}
- Minutes last week: {stats.get('minutes_last_week', 0)}
- Total sessions this week: {stats.get('total_sessions', 0)}
- Completed sessions: {stats.get('completed_sessions', 0)}
- Stopped early sessions: {stats.get('stopped_early_sessions', 0)}
- Abandoned sessions: {stats.get('abandoned_sessions', 0)}
- Current streak: {stats.get('current_streak', 0)}
- Longest streak: {stats.get('longest_streak', 0)}

Category breakdown (minutes):
"""

        # Add category breakdown
        by_category = stats.get('by_category', {})
        if by_category:
            for cat, mins in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
                user_content += f"- {cat}: {mins}\n"
        else:
            user_content += "- (no categories recorded)\n"

        user_content += "\nProject breakdown (minutes):\n"
        by_project = stats.get('by_project', {})
        if by_project:
            for proj, mins in sorted(by_project.items(), key=lambda x: x[1], reverse=True):
                user_content += f"- {proj}: {mins}\n"
        else:
            user_content += "- (no projects recorded)\n"

        user_content += "\nWeekday breakdown (minutes):\n"
        by_weekday = stats.get('by_weekday', {})
        weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for day_name in weekday_names:
            mins = by_weekday.get(day_name, 0)
            user_content += f"- {day_name}: {mins}\n"

        user_content += "\nUser profile (if available):\n"
        if user.get('first_name'):
            user_content += f"- First name: {user.get('first_name')}\n"
        if user.get('organization'):
            user_content += f"- Organization: {user.get('organization')}\n"
        user_content += f"- Timezone: {stats.get('timezone', 'UTC')}\n"

        user_content += """
Please return a short HTML fragment using <h2>, <p>, and <ul>/<li> only, with:

1) A quick overview of the week.
2) One paragraph on focus patterns (categories, days).
3) One paragraph on discipline (completed vs abandoned, honest but not shaming).
4) If there are named projects, a short note on where most of their time went.
5) 3 concrete recommendations for next week in a bullet list.

Don't include <html> or <body> tags. Don't mention that you are an AI."""

        # Make API request
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": OPENAI_TEMPERATURE,
            "max_tokens": OPENAI_MAX_TOKENS_WEEKLY,
        }

        response = requests.post(
            OPENAI_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code >= 200 and response.status_code < 300:
            data = response.json()
            ai_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if ai_content:
                print(f"[Deepmode AI Weekly] Generated AI summary for {user.get('email', 'user')}")
                return ai_content.strip()
            else:
                print(f"[Deepmode AI Weekly] Empty response from OpenAI for {user.get('email', 'user')}")
                return ""
        else:
            print(f"[Deepmode AI Weekly] OpenAI API error: HTTP {response.status_code} - {response.text}")
            return ""

    except Exception as e:
        print(f"[Deepmode AI Weekly] Error generating AI summary for {user.get('email', 'user')}: {e}")
        return ""

