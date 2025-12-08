# app/email_utils.py

import os
import requests

# MailerSend configuration from environment
MAILERSEND_API_KEY = os.getenv("MAILERSEND_API_KEY", "")
MAILERSEND_FROM_EMAIL = os.getenv("MAILERSEND_FROM_EMAIL", "hi@deepmode.app")
MAILERSEND_FROM_NAME = os.getenv("MAILERSEND_FROM_NAME", "Deepmode")

# Email sending control
EMAIL_SENDING_ENABLED = os.getenv("EMAIL_SENDING_ENABLED", "true").lower() == "true"

# Base URL for email links
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
DASHBOARD_URL = f"{BASE_URL}/dashboard"
STREAK_URL = f"{BASE_URL}/streak"
PRICING_URL = f"{BASE_URL}/#pricing"
EMAIL_PREFS_URL = DASHBOARD_URL  # Email preferences accessed via dashboard


def _build_email_footer(is_pro: bool = False) -> str:
    """
    Build consistent email footer with dashboard CTA and unsubscribe link.
    
    Args:
        is_pro: Whether the user is a Pro user (affects CTA text and link)
    
    Returns:
        HTML footer string
    """
    if is_pro:
        insights_text = "View your full insights, streaks, graphs and AI analysis anytime on your dashboard."
        cta_link = DASHBOARD_URL
        cta_text = "View dashboard"
    else:
        insights_text = "See more insights and unlock AI-powered reports on your dashboard."
        cta_link = PRICING_URL
        cta_text = "Upgrade to Pro"
    
    return f"""
<hr style="border:none;border-top:1px solid #27272f;margin:24px 0;" />
<p style="font-size:12px;color:#9ca3af;line-height:1.6;margin:0 0 6px;">
  {insights_text} <a href="{cta_link}" style="color:#e50914;text-decoration:underline;">{cta_text}</a>.
</p>
<p style="font-size:11px;color:#6b7280;margin:0;">
  To manage what we send you, visit your profile settings and update your <a href="{EMAIL_PREFS_URL}" style="color:#9ca3af;text-decoration:underline;">email preferences</a>.
</p>
"""


def _build_email_footer_text(is_pro: bool = False) -> str:
    """
    Build plain text footer for email fallbacks.
    
    Args:
        is_pro: Whether the user is a Pro user (affects CTA text and link)
    
    Returns:
        Plain text footer string
    """
    if is_pro:
        insights_text = "View your full insights, streaks, graphs and AI analysis anytime on your dashboard."
        cta_link = DASHBOARD_URL
        cta_text = "View dashboard"
    else:
        insights_text = "See more insights and unlock AI-powered reports on your dashboard."
        cta_link = PRICING_URL
        cta_text = "Upgrade to Pro"
    
    return f"\n\n{insights_text}\n\n{cta_text}: {cta_link}\n\nTo manage what we send you, visit your email preferences in your profile settings: {EMAIL_PREFS_URL}"


def _send_via_mailersend(to_email: str, subject: str, html_body: str, text_fallback: str | None = None, is_pro: bool = False) -> None:
    """
    Send email via MailerSend HTTP API.
    Non-blocking, never raises exceptions.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML email body (footer will be appended)
        text_fallback: Plain text fallback (footer will be appended)
        is_pro: Whether user is Pro (for footer CTA)
    """
    if not EMAIL_SENDING_ENABLED or not MAILERSEND_API_KEY:
        print(f"[Deepmode] Email sending disabled or MailerSend not configured. Skipping send to {to_email} ({subject})")
        return

    # Append footer to HTML
    html_body = html_body.rstrip() + _build_email_footer(is_pro=is_pro)
    
    # Append footer to text fallback
    if not text_fallback:
        text_fallback = "Open this email in an HTML-capable client to view the content."
    text_fallback = text_fallback.rstrip() + _build_email_footer_text(is_pro=is_pro)

    url = "https://api.mailersend.com/v1/email"
    headers = {
        "Authorization": f"Bearer {MAILERSEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": {
            "email": MAILERSEND_FROM_EMAIL,
            "name": MAILERSEND_FROM_NAME,
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "text": text_fallback,
        "html": html_body,
        "unsubscribe_url": EMAIL_PREFS_URL,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code >= 200 and response.status_code < 300:
            print(f"[Deepmode] Email sent to {to_email} with subject: {subject}")
        else:
            print(f"[Deepmode] Error sending email to {to_email}: HTTP {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[Deepmode] Error sending email to {to_email}: {e}")


def send_email_html(
    to_email: str,
    subject: str,
    html_body: str,
    text_fallback: str | None = None,
    is_pro: bool = False,
) -> None:
    """
    Generic HTML email helper used by welcome + password-changed emails.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML email body (footer will be appended automatically)
        text_fallback: Plain text fallback (footer will be appended automatically)
        is_pro: Whether user is Pro (for footer CTA, defaults to False)
    """
    _send_via_mailersend(to_email, subject, html_body, text_fallback, is_pro=is_pro)


def _build_verification_email(to_email: str, token: str) -> tuple[str, str, str]:
    """
    Build verification email content.
    Returns (subject, text_body, html_body).
    """
    verify_link = f"{BASE_URL}/auth/verify?token={token}"

    subject = "Verify your Deepmode account"

    text_body = f"""Welcome to Deepmode.

Verify your email to unlock weekly focus reports and protect your streak:
{verify_link}

Once verified, Deepmode can safely send you weekly and daily summaries of your deep work.

If you didn't request this, you can ignore this email.

— Deepmode
"""

    html_body = f"""\
<html>
  <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
    <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
        Deepmode
      </div>
      <h1 style="font-size:20px;margin:0 0 12px;font-weight:600;">Verify your email</h1>
      <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
        Verify your email to unlock weekly reports and protect your streak.
      </p>
      <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
        Once verified, Deepmode can keep your streak safe and send you weekly and daily summaries of your deep work.
      </p>
      <p style="margin:0 0 20px;">
        <a href="{verify_link}"
           style="display:inline-block;background:#e50914;color:#ffffff;text-decoration:none;
                  padding:10px 18px;border-radius:999px;font-size:14px;font-weight:500;">
          Verify my account
        </a>
      </p>
      <p style="font-size:12px;color:#9ca3af;margin:0 0 20px;line-height:1.6;">
        Or paste this link into your browser:<br/>
        <span style="color:#e5e7eb;font-size:11px;word-break:break-all;">{verify_link}</span>
      </p>
      <hr style="border:none;border-top:1px solid #27272f;margin:20px 0;" />
      <p style="font-size:11px;color:#6b7280;margin:0;">
        If you didn't request this, you can ignore this email.
      </p>
    </div>
  </body>
</html>
"""

    return (subject, text_body, html_body)


def send_verification_email(to_email: str, token: str) -> None:
    subject, text_body, html_body = _build_verification_email(to_email, token)
    send_email_html(to_email, subject, html_body, text_body, is_pro=False)


def send_welcome_email(to_email: str) -> None:
    """
    Send the initial welcome email when a user signs up.
    This is separate from the verification email.
    """
    if not to_email:
        return

    subject = "Welcome to Deepmode"

    # Use BASE_URL for login/dashboard links
    login_link = f"{BASE_URL}/login"
    docs_link = f"{BASE_URL}/"  # landing

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;">Welcome to Deepmode</h1>

        <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
          You've created your Deepmode account. From now on, your deep work has a home.
        </p>

        <h2 style="margin:0 0 12px;font-size:16px;font-weight:600;color:#e5e7eb;">Next steps (takes 2 minutes):</h2>
        <ul style="margin:0 0 20px 18px;font-size:14px;line-height:1.8;color:#9ca3af;padding-left:0;list-style-position:outside;">
          <li style="margin-bottom:8px;">Install the Chrome extension and pin it in your toolbar.</li>
          <li style="margin-bottom:8px;">Start a 25-minute session and stay in Deepmode until the timer ends.</li>
          <li style="margin-bottom:8px;">Assign a project name (e.g. 'Thesis', 'Client A', 'Interview prep') to the completed sessions to track the Projects you are currenlty working on.</li>
        </ul>

        <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#9ca3af;">
          Deepmode is built for people who can't afford to waste their attention — professionals and serious students. One focused session of work beats a whole day of multitasking
        </p>

        <p style="margin:0 0 20px;">
          <a href="{login_link}"
             style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                    color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
            Go to my dashboard
          </a>
        </p>

      </div>
    </div>
    """

    text_body = (
        "Welcome to Deepmode.\n\n"
        "You've created your Deepmode account. From now on, your deep work has a home.\n\n"
        "Next steps (takes 2 minutes):\n"
        "1) Install the Chrome extension and pin it in your toolbar.\n"
        "2) Start a 25-minute session and stay in Deepmode until the timer ends.\n"
        "3) Assign a project name (e.g. 'Thesis', 'Client A', 'Interview prep') to the completed sessions to track the Projects you are currenlty working on.\n\n"
        "Deepmode is built for people who can't afford to waste their attention — professionals and serious students. One focused session of work beats a whole day of multitasking.\n\n"
        "Go to your dashboard: " + login_link
    )

    send_email_html(to_email, subject, html_body, text_body, is_pro=False)


def send_reset_email(to_email: str, token: str) -> None:
    """
    Send the "forgot password" email with reset link.
    """
    reset_link = f"{BASE_URL}/auth/reset-password?token={token}"

    subject = "Reset your Deepmode password"

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Reset your password</h1>
        <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
          You asked to reset the password for your Deepmode account.
        </p>
        <p style="margin:0 0 20px;">
          <a href="{reset_link}"
             style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                    color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
            Set a new password
          </a>
        </p>
        <p style="font-size:12px;color:#9ca3af;margin:0 0 12px;line-height:1.6;">
          This link will expire in about an hour. If you didn't request this, you can ignore this email — your account stays unchanged.
        </p>
        <p style="font-size:11px;color:#6b7280;margin:0;">
          For security, never share this link with anyone.
        </p>
      </div>
    </div>
    """

    text_body = (
        "Reset your Deepmode password\n\n"
        "You asked to reset the password for your Deepmode account.\n\n"
        "Set a new password: " + reset_link + "\n\n"
        "This link will expire in about an hour. If you didn't request this, you can ignore this email — your account stays unchanged.\n\n"
        "For security, never share this link with anyone."
    )

    send_email_html(to_email, subject, html_body, text_body, is_pro=False)


def send_daily_streak_email(
    to_email: str,
    current_streak: int,
    longest_streak: int,
    minutes_yesterday: int,
) -> None:
    subject = f"Deepmode • Day {current_streak} of your focus streak"
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Day {current_streak} of your focus streak</h1>
        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          Yesterday you logged <strong>{minutes_yesterday} minutes</strong> of deep work.
        </p>
        <p style="font-size:13px;line-height:1.6;margin:0 0 20px;color:#9ca3af;">
          Longest streak so far: <strong>{longest_streak} day{'s' if longest_streak != 1 else ''}</strong>.
        </p>
        <p style="font-size:12px;color:#9ca3af;margin:0 0 20px;font-style:italic;line-height:1.6;">
          Your streak measures one thing: how often you sit down and finish a focused block — not how "motivated" you felt.
        </p>
        <a href="https://deepmode.app/login"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Start today's first block
        </a>
      </div>
    </div>
    """
    # Daily emails are only sent to Pro users
    send_email_html(to_email, subject, body, is_pro=True)


def send_weekly_summary_email(
    to_email: str,
    minutes_this_week: int,
    minutes_last_week: int,
    total_sessions: int,
    completed_sessions: int,
    current_streak: int,
    longest_streak: int,
) -> None:
    delta = minutes_this_week - minutes_last_week
    sign = "+" if delta >= 0 else "−"
    delta_abs = abs(delta)

    subject = "Deepmode • Your weekly focus report"
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Your weekly focus report</h1>

        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          This week: <strong>{minutes_this_week} minutes</strong> of deep work.
        </p>
        <p style="font-size:13px;line-height:1.6;margin:0 0 12px;color:#9ca3af;">
          Last week: <strong>{minutes_last_week} minutes</strong> ({sign}{delta_abs} minutes change).
        </p>

        <p style="font-size:13px;line-height:1.6;margin:0 0 12px;color:#9ca3af;">
          Sessions completed: <strong>{completed_sessions}</strong> out of {total_sessions} started.
        </p>

        <p style="font-size:13px;line-height:1.6;margin:0 0 20px;color:#9ca3af;">
          Current streak: <strong>{current_streak} day{'s' if current_streak != 1 else ''}</strong> • Longest streak: <strong>{longest_streak} day{'s' if longest_streak != 1 else ''}</strong>
        </p>

        <p style="font-size:12px;color:#9ca3af;margin:0 0 20px;font-style:italic;line-height:1.6;">
          Use this as a scoreboard, not a judgment. The only move that matters is the next finished block.
        </p>

        <a href="https://deepmode.app/login"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Open dashboard
        </a>

      </div>
    </div>
    """
    # Weekly summary emails are only sent to Pro users
    send_email_html(to_email, subject, body, is_pro=True)


def send_minimal_weekly_summary_email(
    to_email: str,
    minutes_this_week: int,
    total_sessions: int,
    completed_sessions: int,
    days_worked: int,
    current_streak: int,
    top_project_name: str | None = None,
    top_project_minutes: int | None = None,
    top_category_name: str | None = None,
) -> None:
    """
    Enhanced weekly summary for Free users (no AI).
    Includes real stats and clear Pro upsell.
    """
    subject = "Deepmode • Your week at a glance"
    
    # Build stats section
    stats_html = f"""
        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          This week: <strong>{minutes_this_week} minutes</strong> of deep work.
        </p>
        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          Sessions: <strong>{completed_sessions} completed</strong> out of <strong>{total_sessions} started</strong>.
        </p>
        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          Days worked: <strong>{days_worked} out of 7</strong>.
        </p>
    """
    
    if top_project_name and top_project_minutes:
        stats_html += f"""
        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          Top project: <strong>{escape_html(top_project_name)}</strong> — {top_project_minutes} minutes.
        </p>
        """
    
    if top_category_name:
        stats_html += f"""
        <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
          Main focus: <strong>{escape_html(top_category_name)}</strong>.
        </p>
        """
    else:
        stats_html += '<p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;"></p>'
    
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Your week at a glance</h1>

        {stats_html}

        <p style="font-size:13px;line-height:1.6;margin:0 0 20px;color:#9ca3af;font-style:italic;">
          Use this as a simple scoreboard, not a judgment. The only move that matters is your next finished block.
        </p>

        <hr style="border:none;border-top:1px solid #27272f;margin:24px 0;" />

        <h2 style="font-size:16px;font-weight:600;margin:0 0 12px;color:#e5e7eb;">Upgrade to Deepmode AI Pro</h2>
        <p style="font-size:13px;line-height:1.6;margin:0 0 20px;color:#9ca3af;">
          Pro unlocks AI-written weekly reports based on your actual sessions, deeper project and category breakdowns, and a momentum score with next-week recommendations.
        </p>

        <a href="https://deepmode.app/#pricing"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Unlock AI focus reports
        </a>

      </div>
    </div>
    """
    # Minimal weekly emails are for Free users
    send_email_html(to_email, subject, body, is_pro=False)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def send_pro_welcome_email(to_email: str) -> None:
    """
    Fire-and-forget helper to send the Deepmode AI Pro welcome email.
    Call this ONLY when a user is upgraded from free -> Pro.
    """
    if not to_email:
        return

    subject = "Welcome to Deepmode AI Pro"

    html_body = """
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="color:#e50914;margin:0 0 12px;font-size:24px;font-weight:600;">
          Welcome to Deepmode AI Pro
        </h1>

        <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#e5e7eb;">
          You've just turned Deepmode into a full focus system — not just a timer.
        </p>

        <h2 style="margin:18px 0 12px;font-size:16px;font-weight:600;color:#e5e7eb;">What you've unlocked</h2>

        <ul style="margin:0 0 20px 18px;font-size:14px;line-height:1.8;color:#9ca3af;padding-left:0;list-style-position:outside;">
          <li style="margin-bottom:8px;">Unlimited deepwork sessions and custom blocks.</li>
          <li style="margin-bottom:8px;">Project and category-level tracking.</li>
          <li style="margin-bottom:8px;">AI-powered weekly and daily reports that highlight patterns and next actions.</li>
          <li style="margin-bottom:8px;">Streak insights that show how consistently you protect focus.</li>
        </ul>

        <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#9ca3af;">
          Treat Deepmode like a gym for your attention. Show up, finish the block, let the data compound.
        </p>

        <p style="margin:0 0 20px;">
          <a href="https://deepmode.app/login"
             style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                    color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
            Start a Pro session
          </a>
        </p>

      </div>
    </div>
    """

    text_body = (
        "Welcome to Deepmode AI Pro\n\n"
        "You've just turned Deepmode into a full focus system — not just a timer.\n\n"
        "What you've unlocked:\n"
        "- Unlimited deepwork sessions and custom blocks\n"
        "- Project and category-level tracking\n"
        "- AI-powered weekly and daily reports that highlight patterns and next actions\n"
        "- Streak insights that show how consistently you protect focus\n\n"
        "Treat Deepmode like a gym for your attention. Show up, finish the block, let the data compound.\n\n"
        "Start a Pro session: https://deepmode.app/login"
    )

    send_email_html(to_email, subject, html_body, text_body, is_pro=True)


def send_ai_weekly_summary_email(
    to_email: str,
    stats: dict,
    ai_html: str,
) -> None:
    """
    Send AI-enhanced weekly summary email for Pro users.
    Includes numeric snapshot + AI narrative + CTA.
    """
    minutes_this_week = stats.get("minutes_this_week", 0)
    minutes_last_week = stats.get("minutes_last_week", 0)
    total_sessions = stats.get("total_sessions", 0)
    completed_sessions = stats.get("completed_sessions", 0)
    current_streak = stats.get("current_streak", 0)
    longest_streak = stats.get("longest_streak", 0)

    delta = minutes_this_week - minutes_last_week
    sign = "+" if delta >= 0 else "−"
    delta_abs = abs(delta)

    subject = "Deepmode • Your weekly focus report"
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Your weekly focus report</h1>

        <div style="background:#18181f;border-radius:8px;padding:16px;margin:0 0 20px;border:1px solid #27272f;">
          <p style="font-size:14px;line-height:1.6;margin:0 0 8px;color:#e5e7eb;">
            This week: <strong>{minutes_this_week} minutes</strong> of deep work.
          </p>
          <p style="font-size:13px;line-height:1.6;margin:0 0 8px;color:#9ca3af;">
            Last week: <strong>{minutes_last_week} minutes</strong> ({sign}{delta_abs} minutes change).
          </p>
          <p style="font-size:13px;line-height:1.6;margin:0 0 8px;color:#9ca3af;">
            <strong>{completed_sessions} completed</strong> out of {total_sessions} started.
          </p>
          <p style="font-size:13px;line-height:1.6;margin:0;color:#9ca3af;">
            Current streak: <strong>{current_streak} day{'s' if current_streak != 1 else ''}</strong> • Longest: <strong>{longest_streak} day{'s' if longest_streak != 1 else ''}</strong>
          </p>
        </div>

        <div style="margin:0 0 20px;padding:16px 0;border-top:1px solid #27272f;border-bottom:1px solid #27272f;">
          {ai_html}
        </div>

        <a href="https://deepmode.app/login"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Open Deepmode and start a 25-minute block
        </a>
      </div>
    </div>
    """
    # AI weekly emails are only sent to Pro users
    send_email_html(to_email, subject, body, is_pro=True)


def send_ai_daily_email(
    to_email: str,
    daily_stats: dict,
    ai_html: str,
) -> None:
    """
    Send AI-enhanced daily email for Pro users.
    Short, focused recap with AI commentary.
    """
    minutes_yesterday = daily_stats.get("minutes_yesterday", 0)
    sessions_yesterday = daily_stats.get("sessions_yesterday", 0)
    current_streak = daily_stats.get("current_streak", 0)

    subject = "Deepmode • Yesterday's focus in one glance"
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Yesterday's focus in one glance</h1>
        <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
          Yesterday you logged <strong>{minutes_yesterday} minutes</strong> across <strong>{sessions_yesterday} session{'s' if sessions_yesterday != 1 else ''}</strong>.
        </p>

        <div style="margin:0 0 20px;padding:16px 0;border-top:1px solid #27272f;border-bottom:1px solid #27272f;">
          {ai_html}
        </div>

        <a href="https://deepmode.app/login"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Start today's first block
        </a>

      </div>
    </div>
    """
    # AI daily emails are only sent to Pro users
    send_email_html(to_email, subject, body, is_pro=True)


def send_pro_cancellation_email(to_email: str) -> None:
    """
    Supportive downgrade email when a user loses Pro
    (subscription cancelled / expired / payment failed).
    No guilt, just honest encouragement.
    """
    if not to_email:
        return

    subject = "Deepmode AI Pro cancelled — your focus work doesn't have to be"

    html_body = """
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#e5e7eb;">
          Deepmode AI Pro is off — your focus work doesn't have to be.
        </h1>

        <p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#e5e7eb;">
          Your Deepmode AI Pro subscription has ended. The sessions you've already finished still count, and your free account is still active.
        </p>

        <p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#9ca3af;">
          You can keep using Deepmode to run focused blocks and maintain your streak. The rule is the same either way: small, finished sessions beat "trying to be productive all day."
        </p>

        <p style="margin:0 0 20px;font-size:14px;line-height:1.6;color:#9ca3af;">
          If you ever want Pro back — AI reports, advanced insights, and unlimited history — you can upgrade in a few clicks from your dashboard.
        </p>

        <p style="font-size:11px;color:#6b7280;margin:0;">
          Thanks for using Deepmode and for taking your focus seriously.
        </p>
      </div>
    </div>
    """

    text_body = (
        "Deepmode AI Pro cancelled — your focus work doesn't have to be\n\n"
        "Your Deepmode AI Pro subscription has ended. The sessions you've already finished still count, and your free account is still active.\n\n"
        "You can keep using Deepmode to run focused blocks and maintain your streak. The rule is the same either way: small, finished sessions beat 'trying to be productive all day.'\n\n"
        "If you ever want Pro back — AI reports, advanced insights, and unlimited history — you can upgrade in a few clicks from your dashboard.\n\n"
        "Thanks for using Deepmode and for taking your focus seriously."
    )

    # Cancellation email - user was Pro, but now they're not, so use is_pro=False
    send_email_html(to_email, subject, html_body, text_body, is_pro=False)
