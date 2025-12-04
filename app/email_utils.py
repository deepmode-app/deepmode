# app/email_utils.py

import smtplib
from email.message import EmailMessage
import os

SMTP_HOST = "smtp.zoho.eu"
SMTP_PORT = 587  # TLS
SMTP_USER = "hi@deepmode.app"
SMTP_PASSWORD = "UftwHcwBBNZe"
print(
    "[Deepmode SMTP] Host:", SMTP_HOST,
    "| User:", SMTP_USER,
    "| pw_len:", len(SMTP_PASSWORD or "")
)


BASE_URL = "http://127.0.0.1:8000"  # change to https://deepmode.app in prod


def _send_email_message(msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            print("[Deepmode SMTP] Host:", SMTP_HOST, "User:", SMTP_USER)
            print("[Deepmode SMTP] Password length:", len(SMTP_PASSWORD))
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[Deepmode] Email sent to {msg['To']} with subject: {msg['Subject']}")
    except Exception as e:
        print(f"[Deepmode] Error sending email to {msg['To']}: {e}")


def send_email_html(
    to_email: str,
    subject: str,
    html_body: str,
    text_fallback: str | None = None,
) -> None:
    """
    Generic HTML email helper used by welcome + password-changed emails.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    if not text_fallback:
        text_fallback = "Open this email in an HTML-capable client to view the content."

    msg.set_content(text_fallback)
    msg.add_alternative(html_body, subtype="html")

    _send_email_message(msg)


def _build_verification_email(to_email: str, token: str) -> EmailMessage:
    verify_link = f"{BASE_URL}/auth/verify?token={token}"

    msg = EmailMessage()
    msg["Subject"] = "Verify your Deepmode account"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    text_body = f"""Welcome to Deepmode.

Verify your account to start protecting your focus:
{verify_link}

Once verified, you'll be able to start deepwork blocks, track your progress, and build your discipline score.

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
      <h1 style="font-size:20px;margin:0 0 12px;font-weight:600;">Welcome to Deepmode</h1>
      <p style="font-size:14px;line-height:1.6;margin:0 0 20px;color:#e5e7eb;">
        Verify your account to start protecting your focus and tracking your deep work.
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
      <p style="font-size:12px;color:#9ca3af;margin:0 0 8px;line-height:1.6;">
        Once verified, you'll be able to start deepwork blocks, track your progress, and build your discipline score.
      </p>
      <p style="font-size:11px;color:#6b7280;margin:0;">
        If you didn't request this, you can ignore this email.
      </p>
    </div>
  </body>
</html>
"""

    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def send_verification_email(to_email: str, token: str) -> None:
    msg = _build_verification_email(to_email, token)
    _send_email_message(msg)


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
        This link will expire in about an hour. If you didn’t request this,
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
        "You’ve unlocked:\n"
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

    subject = "Deepmode Pro cancelled — your discipline doesn’t have to be"

    html_body = """
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
                background-color:#050509;padding:24px;color:#f5f5f5;">
      <h1 style="margin:0 0 12px;font-size:22px;">
        Deepmode Pro is off — your focus work doesn’t have to be.
      </h1>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        Your Pro subscription has ended. No drama, no hard feelings.
      </p>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        The blocks you’ve already finished still count. You proved you can sit down,
        shut the noise off and move real work forward.
      </p>

      <p style="margin:0 0 12px;font-size:14px;line-height:1.6;">
        Whether you stay on the free plan or come back to Pro later, the rule is the same:
        <strong>small, finished focus blocks compound more than “trying to be productive all day”.</strong>
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
        "small, finished focus blocks compound faster than endless “productive” scrolling.\n\n"
        "Keep going in whatever setup works for you.\n"
        "— Deepmode\n"
    )

    send_email_html(to_email, subject, html_body, text_body)
