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

1. Today's Snapshot
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

7. Tomorrow's Plan
   Give exactly 2 tiny tactical actions for the user to implement next.

STYLE RULES

- No emojis.
- No filler.
- Short, sharp sentences.
- Sound like a high-performance advisor.
- Never apologise.
- Never fabricate data.
- Never exceed the section structure.
- Do not repeat the exact same suggestion in multiple sections. If you have already suggested naming sessions by project, do not repeat that sentence in 'Project & Category Insights' or 'Opportunities'.
- Each section (What's Working, Opportunities, etc.) should be 2–4 sentences. Avoid run-on paragraphs.

PROJECT & CATEGORY INSIGHTS RULES

- Focus on the top 1–2 projects (by minutes), and the top 1–2 categories.
- If there are no project names, mention that once, briefly, and then move on. Do not turn that section into generic advice.
- Do not repeat earlier suggestions about naming projects if you've already mentioned it.

LOW DATA / NEW USER HANDLING

- If the user has very little data (first few days or very low minutes), keep the tone direct but encouraging:
  - Acknowledge that volume is low.
  - Emphasise that they're at the starting line and the goal now is building reps and consistency, not perfection.
- Never use guilt or shame. You are a performance coach, not a motivational speaker.
- The Momentum Score explanation must never contradict the "early days" framing for new/low-volume users.

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
- <h2> for section headings (e.g., <h2>Today's Snapshot</h2>)
- <p> for paragraphs
- <ul> and <li> for lists
- <strong> for emphasis (sparingly)

Do NOT include <html>, <body>, or <head> tags. Return only the content that will be embedded in the email."""

        # Extract stats
        total_minutes = daily_stats.get('minutes_yesterday', 0)
        completed = daily_stats.get('completed_yesterday', 0)
        abandoned = daily_stats.get('abandoned_yesterday', 0)
        stopped_early = daily_stats.get('stopped_early_yesterday', 0)
        sessions_total = daily_stats.get('sessions_yesterday', 0)
        current_streak = daily_stats.get('current_streak', 0)
        longest_streak = daily_stats.get('longest_streak', 0)
        
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
        user_content = f"""You are generating a Deepmode performance report.

Report type: daily.

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

