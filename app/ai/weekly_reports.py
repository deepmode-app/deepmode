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

- When analyzing weekly patterns, pay special attention to weekday (Mon-Fri) performance vs weekend (Sat-Sun).
- Weekday consistency is the professional foundation — celebrate strong weekday patterns.
- Weekend work is optional and valuable when intentional — never frame it as expected or required.
- If the week includes weekends with work, celebrate it as bonus momentum, but emphasize weekday patterns as the core.
- If weekends show lower activity, that's normal and healthy — never suggest it's a problem.

OUTPUT FORMAT (STRICT)

You must always produce these exact sections:

1. This Week's Snapshot (or Today's Snapshot)

   - 1–2 short sentences.

   - Summarise volume (minutes), completion vs abandonment, and streak direction.

   - Do NOT list every number mechanically — interpret them.

   - When sufficient historical data exists (previous week average provided), include ONE comparative sentence contrasting this week's focused minutes against the user's previous average. Example: "Compared to your previous average, you worked +18% more focused minutes this week." Only include if data supports it. Never fabricate percentages.

2. Pattern You Should Know

   - 1–2 sentences.

   - Identify the single most important behavioural pattern (e.g., strong streak but low minutes, heavy context switching, one strong day then drop-off, etc.).
   
   - When analyzing patterns, emphasize weekday performance. If weekdays show strong consistency, highlight that as the professional foundation. Weekend patterns are secondary.

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

7. Next Week's Plan (or Tomorrow's Plan)

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

- <h2> for section headings (e.g., <h2>This Week's Snapshot</h2>)

- <p> for paragraphs

- <ul> and <li> for bullets

- <strong> for emphasis (sparingly)

Do NOT include <html>, <body>, or <head> tags. Return only the content that will be embedded in the app/email."""

        # Compute additional stats for the template
        total_minutes = stats.get('minutes_this_week', 0)
        completed = stats.get('completed_sessions', 0)
        abandoned = stats.get('abandoned_sessions', 0)
        stopped_early = stats.get('stopped_early_sessions', 0)
        total_sessions = stats.get('total_sessions', 0)
        current_streak = stats.get('current_streak', 0)
        longest_streak = stats.get('longest_streak', 0)
        
        # Compute days worked from weekday breakdown
        by_weekday_list = stats.get('by_weekday', [])
        days_worked = sum(1 for day in by_weekday_list if day.get('minutes', 0) > 0)
        
        # Find best and worst days
        best_day = "N/A"
        worst_day = "N/A"
        if by_weekday_list:
            sorted_days = sorted(by_weekday_list, key=lambda x: x.get('minutes', 0), reverse=True)
            if sorted_days and sorted_days[0].get('minutes', 0) > 0:
                best_day = f"{sorted_days[0].get('weekday', 'N/A')}: {sorted_days[0].get('minutes', 0)} min"
            if len(sorted_days) > 1:
                worst_day = f"{sorted_days[-1].get('weekday', 'N/A')}: {sorted_days[-1].get('minutes', 0)} min"
        
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

        # Get previous week average for comparative insight (if available)
        previous_week_avg = stats.get('previous_week_avg_minutes', None)
        previous_week_line = ""
        if previous_week_avg is not None and previous_week_avg > 0:
            previous_week_line = f"Previous week average minutes: {previous_week_avg}"
        else:
            previous_week_line = "Previous week average minutes: Not available (insufficient historical data)"

        # Analyze weekday vs weekend patterns
        weekday_minutes = 0
        weekend_minutes = 0
        weekday_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        weekend_days = ['Sat', 'Sun']
        
        for day_entry in by_weekday_list:
            day_name = day_entry.get('weekday', '')
            mins = day_entry.get('minutes', 0)
            if day_name in weekday_days:
                weekday_minutes += mins
            elif day_name in weekend_days:
                weekend_minutes += mins
        
        weekday_pattern_note = f"Weekday (Mon-Fri) minutes: {weekday_minutes}. Weekend (Sat-Sun) minutes: {weekend_minutes}. Emphasize weekday consistency as the professional foundation. Weekend work is valuable but optional."

        # Build user content with template
        user_content = f"""You are generating a Deepmode performance report.

Report type: weekly.

{weekday_pattern_note}

Here is the user's data for the period:

Total minutes: {total_minutes}
Sessions completed: {completed}
Sessions abandoned: {abandoned}
Streak: {current_streak} days
Longest streak: {longest_streak} days
Days worked: {days_worked} of 7
Best day: {best_day}
Weakest day: {worst_day}

{previous_week_line}

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

