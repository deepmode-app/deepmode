# app/email_utils.py

import smtplib
from email.message import EmailMessage
import os

SMTP_HOST = "smtp.zoho.eu"
SMTP_PORT = 587  # TLS
SMTP_USER = "hi@deepmode.app"
SMTP_PASSWORD = os.getenv("ZOHO_SMTP_PASSWORD", "CHANGE_ME_APP_PASSWORD")

BASE_URL = "http://127.0.0.1:8000"  # change to https://deepmode.app in prod


def _send_email_message(msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[Deepmode] Email sent to {msg['To']} with subject: {msg['Subject']}")
    except Exception as e:
        print(f"[Deepmode] Error sending email to {msg['To']}: {e}")


def send_email_html(to_email: str, subject: str, html_body: str, text_fallback: str | None = None) -> None:
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
    msg["Subject"] = "Verify your Deepmode account (30 seconds, then you’re in)"
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    text_body = f"""Hey,

Welcome to Deepmode. You just told your future self you’re serious about focus.

Before we start blocking your bad habits, we need to confirm this email belongs to you.

Verify your account:
{verify_link}

Once you’re verified, you’ll be able to:
- Start tracked focus blocks from the Chrome extension
- See your minutes of real work add up in the dashboard
- Watch your discipline score climb instead of your screen time

If you didn’t request this, you can ignore the email — nothing else will happen.

See you in your next focus block,
— Deepmode
"""

    html_body = f"""\
<html>
  <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#050509;color:#f9fafb;padding:16px;">
    <div style="max-width:520px;margin:0 auto;background:#111118;border-radius:12px;padding:18px 18px 16px;border:1px solid #27272f;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:6px;">
        Deepmode
      </div>
      <h1 style="font-size:18px;margin:0 0 8px;">Welcome to your new focus muscle.</h1>
      <p style="font-size:13px;line-height:1.6;margin:0 0 10px;">
        You just signed up for Deepmode. Before we start blocking your worst tabs,
        we need to quickly confirm this email belongs to you.
      </p>
      <p style="margin:0 0 12px;">
        <a href="{verify_link}"
           style="display:inline-block;background:#e50914;color:#ffffff;text-decoration:none;
                  padding:8px 14px;border-radius:999px;font-size:13px;font-weight:500;">
          Verify my account
        </a>
      </p>
      <p style="font-size:12px;color:#9ca3af;margin:0 0 10px;">
        Or paste this link into your browser:<br/>
        <span style="color:#e5e7eb;font-size:11px;">{verify_link}</span>
      </p>
      <hr style="border:none;border-top:1px solid #27272f;margin:10px 0;" />
      <p style="font-size:11px;color:#9ca3af;margin:0;">
        Once verified, you’ll be able to:
        <br>– Start tracked focus blocks from the Chrome extension
        <br>– See your minutes of deep work stack up
        <br>– Watch your discipline score climb instead of your screen time
      </p>
      <p style="font-size:11px;color:#6b7280;margin:8px 0 0;">
        Didn’t sign up? You can safely ignore this — no blocks will start without you.
      </p>
      <p style="font-size:11px;color:#9ca3af;margin:10px 0 0;">
        See you on the other side of your next block,<br/>
        <span style="color:#e5e7eb;">— Deepmode</span>
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
