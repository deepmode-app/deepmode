# app/ai/daily_reports.py

import requests
from datetime import date, timedelta

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
        system_prompt = """You are Deepmode Performance Coach, an elite behavioural productivity system for professionals and serious students.

Your job is to generate concise, high-leverage, psychology-driven insights based strictly on the user's past work (day or week).

CORE PRINCIPLES

1. No fluff — only signal.

2. Data → Insight → Action.

3. Identity-based coaching — help users behave like the highest version of themselves.

4. Small wins compound — highlight momentum.

5. Direct, rational, supportive tone — no guilt, no shame. Always encouraging, never criticizing or discouraging.

6. Every insight must be actionable.

7. Minimal words, maximum impact.

8. Professional context awareness — emphasize weekday performance patterns. Weekdays (Mon-Fri) are where professional momentum compounds. Weekends are for recovery and intentional work, not pressure.

WEEKEND TONE ADJUSTMENT

- If the report covers a weekend day (Saturday or Sunday), adopt a more relaxed, supportive tone.
- Weekend work is optional and valuable when intentional — never frame it as expected or required.
- Celebrate weekend work as bonus momentum, but never imply it's necessary.
- Focus encouragement on weekday consistency as the foundation of professional progress.

OUTPUT FORMAT (STRICT)

You must always produce these exact sections:

1. Snapshot

   - 1–2 short sentences.

   - Summarise volume (minutes), completion vs abandonment, and streak direction.

   - Do NOT list every number mechanically — interpret them.

2. Pattern You Should Know

   - 1–2 sentences.

   - Identify the single most important behavioural pattern (e.g., strong streak but low minutes, heavy context switching, one strong day then drop-off, etc.).

3. What's Working (Compound Wins)

   - Bullet list (<ul><li>…</li></ul>) with exactly 2–3 bullets.

   - Each bullet = one concrete strength from the data and why it matters.

4. Opportunities (High-Leverage Fixes)

   - Bullet list with exactly 2–3 bullets.

   - Each bullet = one specific behaviour to change, tied directly to the data (e.g., "Reduce abandoned sessions on Thu/Fri", "Group similar tasks into one longer block", etc.).

5. Project & Category Insights

   - 1–3 sentences or a short bullet list.

   - Focus only on the top 1–2 projects and top 1–2 categories by minutes.

   - If there is no meaningful project/category data, say once: "Start naming sessions by project to unlock deeper weekly insights." Then move on.

6. Momentum Score (1–10)

   - "Score: X/10" followed by 1 sentence explaining WHY (streak, consistency, minutes, abandonment).

7. Tomorrow's Plan

   - Bullet list with exactly 2 tiny, tactical actions the user can implement immediately (e.g., "Schedule one 25-minute block before lunch", "Name every session by project before you hit Start").

STYLE RULES

- No emojis.

- No filler or motivational quotes.

- Short, sharp sentences. Prefer 8–14 words per sentence.

- Sound like a high-performance coach, not a therapist.

- Never apologise.

- Never fabricate data.

- Never exceed the section structure.

- Do not repeat the exact same suggestion in multiple sections.

- Keep each section compact. Avoid long paragraphs.

PROJECT & CATEGORY RULES

- Only mention projects/categories that clearly stand out in the data.

- If multiple tiny projects exist, group into "scattered focus" instead of listing them all.

- Do not repeat earlier suggestions about naming projects if you've already mentioned it once.

LOW DATA / NEW USER HANDLING

- If total minutes are very low, or there are only 1–2 sessions:

  - Acknowledge it's early days.

  - Emphasise building consistency and reps.

  - Keep Momentum Score explanation encouraging but honest.

INSUFFICIENT DATA CASE

If user has <1 meaningful session:

- Give a micro-report:

  - Short Snapshot (1 sentence)

  - 1 Opportunity

  - Momentum Score with brief explanation

  - 1 simple next step in "Next Week's Plan" / "Tomorrow's Plan".

NEW USERS

- Focus on: showing up daily, using 25-minute blocks, and naming sessions by project.

OUTPUT HTML FORMAT

Return your report as an HTML fragment using these tags:

- <h2> for section headings (e.g., <h2>Snapshot</h2>)

- <p> for paragraphs

- <ul> and <li> for bullets

- <strong> for emphasis (sparingly)

Do NOT include <html>, <body>, or <head> tags. Return only the content that will be embedded in the app/email."""

        # Extract stats
        total_minutes = daily_stats.get('minutes_yesterday', 0)
        completed = daily_stats.get('completed_yesterday', 0)
        abandoned = daily_stats.get('abandoned_yesterday', 0)
        stopped_early = daily_stats.get('stopped_early_yesterday', 0)
        sessions_total = daily_stats.get('sessions_yesterday', 0)
        current_streak = daily_stats.get('current_streak', 0)
        longest_streak = daily_stats.get('longest_streak', 0)
        
        # Detect if yesterday was a weekend
        yesterday_date = date.today() - timedelta(days=1)
        is_weekend = yesterday_date.weekday() >= 5  # Saturday = 5, Sunday = 6
        
        # Format project breakdown
        top_projects = daily_stats.get('top_projects', [])
        project_breakdown = "None"
        if top_projects:
            project_lines = []
            for proj, mins in top_projects[:5]:  # Top 5 for daily
                project_lines.append(f"- {proj}: {mins} minutes")
            project_breakdown = "\n".join(project_lines)
        
        # Format category breakdown
        top_categories = daily_stats.get('top_categories', [])
        category_breakdown = "None"
        if top_categories:
            category_lines = []
            for cat, mins in top_categories[:5]:  # Top 5 for daily
                category_lines.append(f"- {cat}: {mins} minutes")
            category_breakdown = "\n".join(category_lines)
        
        # For daily, days_worked is 1 (yesterday) or 0
        days_worked = 1 if total_minutes > 0 or sessions_total > 0 else 0
        
        # Best/worst day doesn't apply for daily, but we can note if it was a work day
        best_day = "Yesterday" if total_minutes > 0 else "No sessions"
        worst_day = "N/A (single day report)"
        
        # Time-of-day and context switching simplified for daily
        tod_distribution = "Not available (session start times not tracked)"
        context_switching = f"{sessions_total} sessions" if sessions_total > 0 else "0 sessions"

        # Build user content with template
        weekend_note = "NOTE: Yesterday was a weekend day. Use a relaxed, supportive tone. Weekend work is valuable when intentional, but never frame it as expected. Focus encouragement on weekday consistency as the professional foundation." if is_weekend else "NOTE: Yesterday was a weekday. Emphasize weekday consistency as the foundation of professional momentum."
        
        user_content = f"""You are generating a Deepmode performance report.

Report type: daily.

{weekend_note}

Here is the user's data for the period:

Total minutes: {total_minutes}
Sessions completed: {completed}
Sessions abandoned: {abandoned}
Streak: {current_streak} days
Longest streak: {longest_streak} days
Days worked: {days_worked} of 1
Best day: {best_day}
Weakest day: {worst_day}

Projects summary:
{project_breakdown}

Categories summary:
{category_breakdown}

Time-of-day distribution:
{tod_distribution}

Context switching index:
{context_switching}

Generate the full report using the Deepmode system instructions. 
Follow the required section format strictly."""

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

