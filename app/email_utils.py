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


def _send_via_mailersend(to_email: str, subject: str, html_body: str, text_fallback: str | None = None) -> None:
    """
    Send email via MailerSend HTTP API.
    Non-blocking, never raises exceptions.
    """
    if not EMAIL_SENDING_ENABLED or not MAILERSEND_API_KEY:
        print(f"[Deepmode] Email sending disabled or MailerSend not configured. Skipping send to {to_email} ({subject})")
        return

    if not text_fallback:
        text_fallback = "Open this email in an HTML-capable client to view the content."

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
) -> None:
    """
    Generic HTML email helper used by welcome + password-changed emails.
    """
    _send_via_mailersend(to_email, subject, html_body, text_fallback)


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
    send_email_html(to_email, subject, html_body, text_body)


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

        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          You've created your Deepmode account. From now on, your deep work has a home.
        </p>

        <p style="font-size:14px;line-height:1.6;margin:0 0 16px;color:#9ca3af;">
          Next steps:
        </p>
        <ol style="margin:0 0 16px 18px;font-size:13px;line-height:1.6;color:#9ca3af;">
          <li>Install the Chrome extension and pin it in your toolbar.</li>
          <li>Start a 25-minute session and stay in Deepmode until the timer ends.</li>
          <li>Verify your email to unlock weekly focus reports and protect your streak.</li>
        </ol>

        <p style="margin:0 0 16px;">
          <a href="{login_link}"
             style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                    color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
            Go to my dashboard
          </a>
        </p>

        <p style="font-size:11px;color:#6b7280;margin:0;">
          Deep work compounds. One finished session at a time.
        </p>
      </div>
    </div>
    """

    text_body = (
        "Welcome to Deepmode.\n\n"
        "Next steps:\n"
        "1) Install the Chrome extension and pin it.\n"
        "2) Start a 25-minute session and finish it.\n"
        "3) Verify your email to unlock weekly focus reports and protect your streak.\n\n"
        "Go to your dashboard: " + login_link + "\n"
        "Deep work compounds. One finished session at a time.\n"
    )

    send_email_html(to_email, subject, html_body, text_body)


def send_reset_email(to_email: str, token: str) -> None:
    """
    Send the "forgot password" email with reset link.
    """
    reset_link = f"{BASE_URL}/auth/reset-password?token={token}"

    subject = "Reset your Deepmode password"

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                padding:24px;background:#020617;color:#f9fafb;">
      <h1 style="margin:0 0 12px;font-size:20px;">Reset your password</h1>
      <p style="font-size:14px;line-height:1.6;margin:0 0 12px;">
        You asked to reset the password for your Deepmode account.
      </p>
      <p style="margin:0 0 16px;">
        <a href="{reset_link}"
           style="display:inline-block;padding:8px 14px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:13px;font-weight:500;">
          Set a new password
        </a>
      </p>
      <p style="font-size:12px;color:#9ca3af;margin:0 0 6px;">
        This link will expire in about an hour. If you didn't request this,
        you can ignore this email.
      </p>
    </div>
    """

    send_email_html(to_email, subject, html_body)


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
          Longest streak: <strong>{longest_streak} days</strong>.
        </p>
        <p style="font-size:12px;color:#9ca3af;margin:0 0 20px;font-style:italic;line-height:1.6;">
          Your streak reflects your consistency, not your mood.
        </p>
        <a href="https://deepmode.app/login"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Start today's first block
        </a>
        <p style="font-size:11px;color:#6b7280;margin-top:20px;">
          You can turn off daily emails in your email settings.
        </p>
      </div>
    </div>
    """
    send_email_html(to_email, subject, body)


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
          <strong>{completed_sessions} completed</strong> out of {total_sessions} started.
        </p>

        <p style="font-size:13px;line-height:1.6;margin:0 0 20px;color:#9ca3af;">
          Current streak: <strong>{current_streak} days</strong> • Longest: <strong>{longest_streak} days</strong>
        </p>

        <a href="https://deepmode.app/login"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          View dashboard
        </a>

        <p style="font-size:11px;color:#6b7280;margin-top:20px;">
          You can turn off weekly emails in your email settings.
        </p>
      </div>
    </div>
    """
    send_email_html(to_email, subject, body)


def send_minimal_weekly_summary_email(
    to_email: str,
    days_worked: int,
    current_streak: int,
) -> None:
    """
    Minimal weekly summary for Free users.
    Includes only basic stats and upgrade CTA.
    """
    subject = "Deepmode • Your weekly summary"
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="margin:0 0 12px;font-size:20px;font-weight:600;">Your weekly summary</h1>

        <p style="font-size:14px;line-height:1.6;margin:0 0 12px;color:#e5e7eb;">
          You worked <strong>{days_worked} day{'s' if days_worked != 1 else ''}</strong> this week.
        </p>
        <p style="font-size:13px;line-height:1.6;margin:0 0 20px;color:#9ca3af;">
          Current streak: <strong>{current_streak} day{'s' if current_streak != 1 else ''}</strong>
        </p>

        <a href="https://deepmode.app/#pricing"
           style="display:inline-block;padding:10px 18px;border-radius:999px;background:#e50914;
                  color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;">
          Unlock full weekly insights with Deepmode Pro
        </a>

        <p style="font-size:11px;color:#6b7280;margin-top:20px;">
          You can turn off weekly emails in your email settings.
        </p>
      </div>
    </div>
    """
    send_email_html(to_email, subject, body)


def send_pro_welcome_email(to_email: str) -> None:
    """
    Fire-and-forget helper to send the Deepmode Pro welcome email.
    Call this ONLY when a user is upgraded from free -> Pro.
    """
    if not to_email:
        return

    subject = "Welcome to Deepmode Pro"

    html_body = """
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#050509;color:#f9fafb;padding:16px;">
      <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:24px;border:1px solid #27272f;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:12px;font-weight:600;">
          Deepmode
        </div>
        <h1 style="color:#e50914;margin:0 0 12px;font-size:24px;font-weight:600;">
          Welcome to Deepmode Pro
        </h1>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        You now have access to unlimited deepwork blocks, advanced tracking, and detailed progress insights.
      </p>

      <h2 style="margin:18px 0 8px;font-size:16px;">What's included</h2>

      <ul style="margin:0 0 12px 18px;font-size:14px;line-height:1.6;">
        <li>Unlimited deepwork sessions</li>
        <li>Advanced distraction blocking</li>
        <li>Session history and discipline metrics</li>
        <li>Daily and weekly focus reports</li>
        <li>Streak insights</li>
      </ul>

      <p style="margin:0;font-size:14px;line-height:1.6;">
        Start your first Pro block from the Chrome extension.
      </p>
      </div>
    </div>
    """

    text_body = (
        "Deepmode Pro activated — time to build your advantage.\n\n"
        "You've unlocked:\n"
        "- Deep focus blocks (Deepmode, Pomodoro, custom)\n"
        "- Project-based tracking\n"
        "- Smart categories (Design, Research, Study, Fitness, etc.)\n"
        "- Session notes on every block\n"
        "- Streaks, weekly summaries and discipline score\n\n"
        "Use it like a gym for your attention. Welcome to the serious lane.\n"
        "— Deepmode"
    )

    # Correct call – matches send_email_html signature
    send_email_html(to_email, subject, html_body, text_body)


def send_pro_cancellation_email(to_email: str) -> None:
    """
    Supportive downgrade email when a user loses Pro
    (subscription cancelled / expired / payment failed).
    No guilt, just honest encouragement.
    """
    if not to_email:
        return

    subject = "Deepmode Pro cancelled — your discipline doesn't have to be"

    html_body = """
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
                background-color:#050509;padding:24px;color:#f5f5f5;">
      <h1 style="margin:0 0 12px;font-size:22px;">
        Deepmode Pro is off — your focus work doesn't have to be.
      </h1>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        Your Pro subscription has ended. No drama, no hard feelings.
      </p>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        The blocks you've already finished still count. You proved you can sit down,
        shut the noise off and move real work forward.
      </p>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        Whether you stay on the free plan or come back to Pro later, the rule is the same:
        <strong>small, finished focus blocks compound more than "trying to be productive all day".</strong>
      </p>

      <p style="margin:0;font-size:14px;line-height:1.6;">
        Keep going in whatever setup works for you.<br/>
        <span style="color:#e50914;">— Deepmode</span>
      </p>
    </div>
    """

    text_body = (
        "Your Deepmode Pro subscription has ended.\n\n"
        "No guilt — the focus blocks you already finished still count.\n"
        "Whether you stay on the free plan or come back to Pro later, the rule is the same:\n"
        "small, finished focus blocks compound faster than endless \"productive\" scrolling.\n\n"
        "Keep going in whatever setup works for you.\n"
        "— Deepmode\n"
    )

    send_email_html(to_email, subject, html_body, text_body)
