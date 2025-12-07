# app/ai/weekly_reports.py

import requests

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
        system_prompt = """You are Deepmode Performance Coach, an elite behavioural productivity system for professionals and serious students. 

Your job is to generate concise, high-leverage, psychology-driven insights based strictly on the user's past week or past day of work.

CORE PRINCIPLES

1. No fluff — only signal.
2. Data → Insight → Action.
3. Identity-based coaching — help users behave like the highest version of themselves.
4. Small wins compound — highlight momentum.
5. Direct, rational, supportive tone — no guilt, no shame.
6. Every insight must be actionable.
7. Minimal words, maximum impact.

OUTPUT FORMAT (STRICT)

You must always produce these exact sections:

1. This Week's Snapshot (or Today's Snapshot)
   Short factual overview summarising totals, completion rate, and streak pattern.

2. Pattern You Should Know
   Identify the single highest-leverage behavioural pattern in the data.

3. What's Working (Compound Wins)
   List 2 specific strengths demonstrated this period.

4. Opportunities (High-Leverage Fixes)
   List 2 specific improvements that would create the biggest behavioural ROI.

5. Project & Category Insights
   Mention only meaningful insights. 
   If no project/category data exists:
   "Start naming sessions by project to unlock deeper weekly insights."

6. Momentum Score (1–10)
   Score based on streak, consistency, total minutes, stability.
   Always explain the score in one sentence.

7. Next Week's Plan (or Tomorrow's Plan)
   Give exactly 2 tiny tactical actions for the user to implement next.

STYLE RULES

- No emojis.
- No filler.
- Short, sharp sentences.
- Sound like a high-performance advisor.
- Never apologise.
- Never fabricate data.
- Never exceed the section structure.

INSUFFICIENT DATA CASE

If user has <1 meaningful session:
- Give a small snapshot
- 1 opportunity
- Momentum score low but encouraging
- 1 simple next step

NEW USERS

Focus on consistency, naming projects, building routine.

Never mention verification. Never output JSON.

OUTPUT HTML FORMAT

Return your report as an HTML fragment using these tags:
- <h2> for section headings (e.g., <h2>This Week's Snapshot</h2>)
- <p> for paragraphs
- <ul> and <li> for lists
- <strong> for emphasis (sparingly)

Do NOT include <html>, <body>, or <head> tags. Return only the content that will be embedded in the email."""

        # Compute additional stats for the template
        total_minutes = stats.get('minutes_this_week', 0)
        completed = stats.get('completed_sessions', 0)
        abandoned = stats.get('abandoned_sessions', 0)
        stopped_early = stats.get('stopped_early_sessions', 0)
        total_sessions = stats.get('total_sessions', 0)
        current_streak = stats.get('current_streak', 0)
        longest_streak = stats.get('longest_streak', 0)
        
        # Compute days worked from weekday breakdown
        by_weekday = stats.get('by_weekday', {})
        days_worked = sum(1 for day, mins in by_weekday.items() if mins > 0)
        
        # Find best and worst days
        best_day = "N/A"
        worst_day = "N/A"
        if by_weekday:
            sorted_days = sorted(by_weekday.items(), key=lambda x: x[1], reverse=True)
            if sorted_days and sorted_days[0][1] > 0:
                best_day = f"{sorted_days[0][0]}: {sorted_days[0][1]} min"
            if len(sorted_days) > 1:
                worst_day = f"{sorted_days[-1][0]}: {sorted_days[-1][1]} min"
        
        # Format project breakdown
        by_project = stats.get('by_project', {})
        project_breakdown = "None"
        if by_project:
            project_lines = []
            for proj, mins in sorted(by_project.items(), key=lambda x: x[1], reverse=True):
                session_count = 0  # We don't have session count per project in current stats
                project_lines.append(f"- {proj}: {mins} minutes")
            project_breakdown = "\n".join(project_lines)
        
        # Format category breakdown
        by_category = stats.get('by_category', {})
        category_breakdown = "None"
        if by_category:
            category_lines = []
            for cat, mins in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
                category_lines.append(f"- {cat}: {mins} minutes")
            category_breakdown = "\n".join(category_lines)
        
        # Format time-of-day distribution (simplified - we don't have hour-level data)
        tod_distribution = "Not available (session start times not tracked)"
        
        # Compute context switching index (simplified: sessions per day)
        context_switching = "N/A"
        if days_worked > 0 and total_sessions > 0:
            avg_sessions_per_day = total_sessions / days_worked
            context_switching = f"{avg_sessions_per_day:.1f} sessions per active day"

        # Build user content with template
        user_content = f"""You are generating a Deepmode performance report.

Report type: weekly.

Here is the user's data for the period:

Total minutes: {total_minutes}
Sessions completed: {completed}
Sessions abandoned: {abandoned}
Streak: {current_streak} days
Longest streak: {longest_streak} days
Days worked: {days_worked} of 7
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

