# app/ai/daily_reports.py

import requests

from app.ai_config import (
    OPENAI_API_KEY,
    AI_EMAIL_ENABLED,
    OPENAI_API_URL,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS_DAILY,
)


def generate_ai_daily_summary(user, daily_stats: dict) -> str:
    """
    Returns a SHORT HTML snippet for daily email.
    On any error, returns empty string, and caller will fall back to non-AI email.
    """
    if not AI_EMAIL_ENABLED or not OPENAI_API_KEY:
        return ""

    try:
        # Build system prompt
        system_prompt = """You are Deepmode, a brutally honest but supportive focus coach.
You analyze a user's deep work stats for yesterday and write a short daily recap.
Tone: calm, confident, professional, no fluff, no emojis.
You speak directly to "you", not "the user".
Keep it concise: max 200-300 words total."""

        # Build user content with daily stats
        user_content = f"""Yesterday's deep work stats:

- Minutes: {daily_stats.get('minutes_yesterday', 0)}
- Sessions: {daily_stats.get('sessions_yesterday', 0)}
- Completed: {daily_stats.get('completed_yesterday', 0)}
- Abandoned: {daily_stats.get('abandoned_yesterday', 0)}
- Stopped early: {daily_stats.get('stopped_early_yesterday', 0)}
- Current streak: {daily_stats.get('current_streak', 0)}
- Longest streak: {daily_stats.get('longest_streak', 0)}
"""

        # Add top categories
        top_categories = daily_stats.get('top_categories', [])
        if top_categories:
            user_content += "\nTop categories (minutes):\n"
            for cat, mins in top_categories[:3]:  # Top 3
                user_content += f"- {cat}: {mins}\n"

        # Add top projects
        top_projects = daily_stats.get('top_projects', [])
        if top_projects:
            user_content += "\nTop projects (minutes):\n"
            for proj, mins in top_projects[:3]:  # Top 3
                user_content += f"- {proj}: {mins}\n"

        user_content += f"\nTimezone: {daily_stats.get('timezone', 'UTC')}\n"

        user_content += """
Please return a short HTML fragment using <p> and <ul>/<li> only, with:

1) 1-2 sentences summarizing the day.
2) 2-3 bullet points:
   - What they did well.
   - One thing to tighten for today.
   - One concrete suggestion ("Today, protect a single 25-minute block for X.").

Don't include <html> or <body> tags. Don't mention that you are an AI. Keep it brief and actionable."""

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
            "max_tokens": OPENAI_MAX_TOKENS_DAILY,
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
                print(f"[Deepmode AI Daily] Generated AI summary for {user.get('email', 'user')}")
                return ai_content.strip()
            else:
                print(f"[Deepmode AI Daily] Empty response from OpenAI for {user.get('email', 'user')}")
                return ""
        else:
            print(f"[Deepmode AI Daily] OpenAI API error: HTTP {response.status_code} - {response.text}")
            return ""

    except Exception as e:
        print(f"[Deepmode AI Daily] Error generating AI summary for {user.get('email', 'user')}: {e}")
        return ""

