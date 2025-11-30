from datetime import datetime, timedelta, timezone
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import uuid
import os

from app.database import get_conn
from app.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

from app.email_utils import (
    send_verification_email,
    send_reset_email,
    send_email_html
)

# ======================================================
#                   Config Flags
# ======================================================

# Controls whether login is blocked until the user verifies their email.
# Staging: EMAIL_VERIFICATION_REQUIRED=false
# Prod:    EMAIL_VERIFICATION_REQUIRED=true
EMAIL_VERIFICATION_REQUIRED = os.getenv("EMAIL_VERIFICATION_REQUIRED", "true").lower() == "true"

# Base URL for login links in emails (staging vs prod)
# Staging: https://deepmode.onrender.com
# Prod:    https://deepmode.app
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://deepmode.app").rstrip("/")

# Controls whether we actually attempt to send emails (SMTP).
# Staging: EMAIL_SENDING_ENABLED=false
# Prod:    EMAIL_SENDING_ENABLED=true
EMAIL_SENDING_ENABLED = os.getenv("EMAIL_SENDING_ENABLED", "true").lower() == "true"

router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBearer()


# ======================================================
#                   Pydantic Models
# ======================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class EmailPreferences(BaseModel):
    daily_email_enabled: bool
    weekly_email_enabled: bool


# ======================================================
#                   Register Route
# ======================================================

@router.post("/register")
def register(payload: RegisterRequest):
    conn = get_conn()
    cur = conn.cursor()

    email = payload.email.lower()

    # Check existing account
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists.",
        )

    pw_hash = hash_password(payload.password)

    verification_token = str(uuid.uuid4())
    verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    cur.execute(
        """
        INSERT INTO users (
            email,
            password_hash,
            is_pro,
            is_verified,
            verification_token,
            verification_expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (email, pw_hash, False, False, verification_token, verification_expires_at),
    )

    conn.commit()
    conn.close()

    # In staging we don't want signup to hang on SMTP.
    if EMAIL_SENDING_ENABLED:
        try:
            send_verification_email(email, verification_token)
        except Exception as e:
            print("Error sending verification email:", e)

    return {
        "message":
            "Account created. Check your inbox to verify your email before logging in. "
            "If you don’t see it, check Spam/Junk and mark it as ‘Not junk’."
    }


# ======================================================
#                Email Verification
# ======================================================

@router.get("/verify")
def verify_email(token: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, email, verification_expires_at, is_verified
        FROM users
        WHERE verification_token = %s
        """,
        (token,),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")

    user_id = row["id"]
    email = row["email"]
    expires_at = row["verification_expires_at"]
    already_verified = row["is_verified"]

    # Expired token
    if expires_at is None or expires_at.replace(tzinfo=None) < datetime.utcnow():
        conn.close()
        raise HTTPException(status_code=400, detail="Verification link has expired.")

    # Not yet verified → mark verified
    if not already_verified:
        cur.execute(
            """
            UPDATE users
            SET
              is_verified = TRUE,
              verification_token = NULL,
              verification_expires_at = NULL
            WHERE id = %s
            """,
            (user_id,),
        )
        conn.commit()

        # Send Welcome email
        welcome_subject = "You’re in — Welcome to Deepmode"
        welcome_body = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                    padding:24px;background:#020617;color:#f9fafb;">
            <h1 style="margin:0 0 12px;font-size:22px;">Welcome to Deepmode 🎉</h1>
            <p style="font-size:14px;line-height:1.6;">
                Your account is confirmed — your focus HQ is officially open.
            </p>
            <a href="{FRONTEND_URL}/login"
                style="display:inline-block;margin-top:14px;padding:10px 18px;
                background:#e50914;color:#ffffff;text-decoration:none;border-radius:999px;
                font-size:14px;">
                Log in to Deepmode
            </a>
        </div>
        """

        if EMAIL_SENDING_ENABLED:
            try:
                send_email_html(email, welcome_subject, welcome_body)
            except Exception as e:
                print("Error sending welcome email:", e)

    conn.close()

    # Success page
    html_success = f"""
    <html>
      <body style="background:#050509;font-family:-apple-system,sans-serif;
                   display:flex;align-items:center;justify-content:center;min-height:100vh;padding:32px;">
        <div style="background:#111118;border-radius:16px;padding:32px;max-width:420px;
                    border:1px solid #27272f;text-align:center;color:#f5f5f5;">

          <h1 style="font-size:22px;margin-bottom:10px;">Email verified 🎉</h1>
          <p style="color:#e5e7eb;font-size:14px;margin-bottom:18px;">
            Your account is ready. Sign in and start your first deepwork block.
          </p>

          <a href="/login"
             style="display:inline-block;padding:10px 18px;background:#e50914;
                    color:#ffffff;border-radius:999px;text-decoration:none;font-size:14px;">
             Go to Login
          </a>
        </div>
      </body>
    </html>
    """

    return HTMLResponse(content=html_success, status_code=200)


# ======================================================
#                        Login
# ======================================================

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()

    email = payload.email.lower()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cur.fetchone()

    conn.close()

    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Debug: log what the server thinks about flags for this login
    print(
        "[Deepmode] LOGIN FLAGS:",
        "EMAIL_VERIFICATION_REQUIRED =", EMAIL_VERIFICATION_REQUIRED,
        "| is_verified =", row["is_verified"]
    )

    # Only block unverified users if the environment requires it.
    if EMAIL_VERIFICATION_REQUIRED and not row["is_verified"]:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email first. Check your inbox.",
        )

    token = create_access_token({
        "sub": row["email"],
        "user_id": row["id"],
        "is_pro": bool(row["is_pro"]),
    })

    return TokenResponse(access_token=token)


# ======================================================
#              Forgot Password (Send Reset Email)
# ======================================================

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    email = payload.email.lower()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = cur.fetchone()

    if row:
        user_id = row["id"]
        reset_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        cur.execute(
            """
            UPDATE users
            SET reset_token = %s,
                reset_token_expires_at = %s
            WHERE id = %s
            """,
            (reset_token, expires_at, user_id),
        )
        conn.commit()

        if EMAIL_SENDING_ENABLED:
            try:
                send_reset_email(email, reset_token)
            except Exception as e:
                print("Error sending reset email:", e)

    conn.close()

    return {
        "message":
            "If an account exists for that email, we’ve sent a reset link. "
            "Check your inbox (and Spam/Junk)."
    }


# ======================================================
#               Reset Password — Form (GET)
# ======================================================

@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(token: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, reset_token_expires_at
        FROM users
        WHERE reset_token = %s
        """,
        (token,),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return HTMLResponse("Invalid reset link", status_code=400)

    expires_at = row["reset_token_expires_at"]

    if expires_at is None or expires_at.replace(tzinfo=None) < datetime.utcnow():
        conn.close()
        return HTMLResponse("Reset link expired", status_code=400)

    conn.close()

    # Render HTML reset page (kept short for message)
    html_form = f"""
    <html>
      <body style="background:#050509;font-family:-apple-system,sans-serif;
                   display:flex;align-items:center;justify-content:center;min-height:100vh;">
        <form method="POST" onsubmit="submitReset(); return false;"
              style="background:#111118;padding:24px;border-radius:14px;
                     color:#fff;max-width:360px;width:100%;">

          <h2>Set a new password</h2>
          <p style="font-size:12px;color:#9ca3af;margin-bottom:12px;">
            Choose a strong password you won’t reuse.
          </p>

          <label>New password</label>
          <input id="password" type="password" style="width:100%;margin-bottom:10px;" />

          <label>Confirm password</label>
          <input id="confirm" type="password" style="width:100%;" />

          <button type="submit"
                  style="width:100%;margin-top:14px;padding:10px;border:none;background:#e50914;
                         color:#fff;border-radius:999px;cursor:pointer;">
            Update password
          </button>

          <div id="msg" style="margin-top:12px;font-size:12px;color:#bbf7d0;display:none;"></div>
          <div id="err" style="margin-top:12px;font-size:12px;color:#fecaca;display:none;"></div>
        </form>

        <script>
          async function submitReset() {{
            const p = document.getElementById("password").value;
            const c = document.getElementById("confirm").value;
            const msg = document.getElementById("msg");
            const err = document.getElementById("err");

            msg.style.display = err.style.display = "none";

            if (!p || !c) {{
              err.textContent = "Please fill both fields.";
              err.style.display = "block";
              return;
            }}

            if (p !== c) {{
              err.textContent = "Passwords don’t match.";
              err.style.display = "block";
              return;
            }}

            if (p.length < 8) {{
              err.textContent = "Password must be at least 8 characters.";
              err.style.display = "block";
              return;
            }}

            const res = await fetch("/auth/reset-password", {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{ token: "{token}", new_password: p }})
            }});

            if (!res.ok) {{
              const d = await res.json().catch(() => ({{}}));
              err.textContent = d.detail || "Could not reset password.";
              err.style.display = "block";
              return;
            }}

            msg.textContent = "Password updated. Redirecting to login…";
            msg.style.display = "block";
            setTimeout(() => window.location.href = "/login", 1500);
          }}
        </script>
      </body>
    </html>
    """

    return HTMLResponse(content=html_form, status_code=200)


# ======================================================
#               Reset Password — Finish (POST)
# ======================================================

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    token = payload.token
    new_pw = payload.new_password

    if len(new_pw) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, email, reset_token_expires_at
        FROM users
        WHERE reset_token = %s
        """,
        (token,),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    expires_at = row["reset_token_expires_at"]
    if expires_at is None or expires_at.replace(tzinfo=None) < datetime.utcnow():
        conn.close()
        raise HTTPException(status_code=400, detail="Reset link expired.")

    user_id = row["id"]
    email = row["email"]

    hashed = hash_password(new_pw)

    cur.execute(
        """
        UPDATE users
        SET password_hash = %s,
            reset_token = NULL,
            reset_token_expires_at = NULL
        WHERE id = %s
        """,
        (hashed, user_id),
    )

    conn.commit()
    conn.close()

    # Send confirmation email
    subject = "Your Deepmode password was changed"
    body = f"""
    <div style="font-family:-apple-system,sans-serif;padding:24px;background:#020617;color:#f9fafb;">
      <h1>Password updated</h1>
      <p>Your Deepmode password for <b>{email}</b> was changed successfully.</p>
    </div>
    """

    if EMAIL_SENDING_ENABLED:
        try:
            send_email_html(email, subject, body)
        except Exception as e:
            print("Error sending reset confirmation:", e)

    return {"message": "Password updated successfully."}


# ======================================================
#                Current User Dependency
# ======================================================

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user_id = payload.get("user_id")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    return {
        "id": row["id"],
        "email": row["email"],
        "is_pro": bool(row["is_pro"]),
        "is_verified": bool(row["is_verified"]),
    }


@router.get("/email-preferences", response_model=EmailPreferences)
def get_email_preferences(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's email notification preferences.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT daily_email_enabled, weekly_email_enabled
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return EmailPreferences(
        daily_email_enabled=bool(row["daily_email_enabled"]),
        weekly_email_enabled=bool(row["weekly_email_enabled"]),
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """
    Lightweight endpoint for the frontend to know:
    - email
    - is_pro
    - is_verified
    """
    return current_user


@router.post("/email-preferences", response_model=EmailPreferences)
def update_email_preferences(
    prefs: EmailPreferences,
    current_user: dict = Depends(get_current_user),
):
    """
    Update daily/weekly email preferences for the current user.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET daily_email_enabled = %s,
            weekly_email_enabled = %s
        WHERE id = %s
        """,
        (
            prefs.daily_email_enabled,
            prefs.weekly_email_enabled,
            user_id,
        ),
    )
    conn.commit()

    conn.close()

    return prefs
