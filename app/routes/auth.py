from datetime import datetime, timedelta, timezone
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import uuid

from app.database import get_conn
from app.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

from app.email_utils import send_verification_email, send_reset_email, send_email_html



router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBearer()


# ---------- Pydantic models ----------

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

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str



# ---------- Register + verify ----------

@router.post("/register")
def register(payload: RegisterRequest):
    """
    Create a new user:
    - store hashed password
    - create email verification token
    - send verification email
    """
    conn = get_conn()
    cur = conn.cursor()

    email = payload.email.lower()

    # Check if email already exists
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            email,
            pw_hash,
            False,     # is_pro
            False,     # is_verified
            verification_token,
            verification_expires_at,
        ),
    )

    row = cur.fetchone()
    user_id = row["id"]

    conn.commit()
    conn.close()

    # Fire off verification email
    try:
        send_verification_email(email, verification_token)
    except Exception as e:
        print("Error sending verification email:", e)

    return {
        "message": "Account created. Check your inbox to verify your email before logging in. If you don’t see it, check Spam/Junk and mark it as ‘Not junk’."
    }

@router.get("/verify")
def verify_email(token: str):
    """
    Verify a user's email using the one-time token.
    Returns a beautiful HTML success page + sends welcome email.
    """
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

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification link.",
        )

    user_id = row["id"]
    email = row["email"]
    expires_at = row["verification_expires_at"]
    already_verified = row["is_verified"]

    # Token expired?
    if expires_at is None or expires_at.replace(tzinfo=None) < datetime.utcnow():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification link has expired. Please request a new one.",
        )

    # If already verified → still show success page (don’t punish returning user)
    if not already_verified:
        cur.execute(
            """
            UPDATE users
            SET is_verified = TRUE,
                verification_token = NULL,
                verification_expires_at = NULL
            WHERE id = %s
            """,
            (user_id,),
        )
        conn.commit()

        # -----------------------
        # SEND WELCOME EMAIL
        # -----------------------
        welcome_subject = "You’re in — Welcome to Deepmode"
        welcome_body = f"""
        <div style="font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                    padding: 24px; background: #020617; color: #f9fafb;">
          <h1 style="margin:0 0 12px; font-size:22px;">Welcome to Deepmode 🎉</h1>
          <p style="font-size:14px; line-height:1.6;">
            Your account is confirmed and your focus HQ is officially open.
          </p>
          <p style="font-size:14px; line-height:1.6; margin:12px 0;">
            Install the Chrome extension and start your first block. 
            Your streak begins today.
          </p>

          <a href="https://deepmode.app/login"
             style="display:inline-block; margin-top:14px; padding:10px 18px;
             background:#e50914; color:#ffffff; text-decoration:none;
             border-radius:999px; font-size:14px;">
             Log in to Deepmode
          </a>

          <p style="font-size:12px; color:#9ca3af; margin-top:18px;">
            Let’s build your deepwork muscle — one block at a time.
          </p>
        </div>
        """

        try:
            send_email_html(email, welcome_subject, welcome_body)
        except Exception as e:
            print("Error sending welcome email:", e)

    conn.close()

    # -----------------------
    # RETURN BEAUTIFUL HTML
    # -----------------------
    html_success_page = f"""
    <html>
      <body style="background:#050509; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; 
                   min-height:100vh; padding:32px; display:flex; align-items:center; justify-content:center;">
        <div style="background:#111118; border-radius:16px; padding:32px; max-width:420px;
                    border:1px solid #27272f; text-align:center; color:#f5f5f5;">
          
          <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.16em; color:#9ca3af; margin-bottom:6px;">
            <div style='width:16px;height:16px;border-radius:999px;border:2px solid #e50914;margin:0 auto;position:relative;'>
              <div style='position:absolute;inset:3px;border-radius:999px;background:#e50914;'></div>
            </div>
            Deepmode
          </div>

          <h1 style="font-size:22px; margin:10px 0 6px;">Email verified 🎉</h1>
          <p style="color:#e5e7eb; font-size:14px; margin-bottom:18px;">
            Your account is ready. Sign in and start your first deepwork block.
          </p>

          <a href="/login"
             style="display:inline-block; padding:10px 18px; background:#e50914; color:#ffffff;
                    border-radius:999px; text-decoration:none; font-size:14px;">
             Go to Login
          </a>

          <p style="color:#9ca3af; font-size:12px; margin-top:18px;">
            Time to make your future self proud.
          </p>
        </div>
      </body>
    </html>
    """

    return HTMLResponse(content=html_success_page, status_code=200)



# ---------- Login ----------

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """
    Log in with email + password (JSON body).
    Return a JWT access token.
    """
    conn = get_conn()
    cur = conn.cursor()

    email = payload.email.lower()
    cur.execute("SELECT * FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    conn.close()

    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not row.get("is_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first. Check your inbox for a message from hi@deepmode.app.",
        )

    token = create_access_token(
        {
            "sub": row["email"],
            "user_id": row["id"],
            "is_pro": bool(row["is_pro"]),
        }
    )

    return TokenResponse(access_token=token)


# ---------- Forgot / Reset password ----------

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    """
    Request a password reset link.
    Always returns 200 with a generic message (no user enumeration).
    """
    email = payload.email.lower()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = cur.fetchone()

    if row is not None:
        user_id = row["id"]
        reset_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        cur.execute(
            """
            UPDATE users
            SET reset_password_token = %s,
                reset_password_expires_at = %s
            WHERE id = %s
            """,
            (reset_token, expires_at, user_id),
        )
        conn.commit()

        try:
            send_reset_email(email, reset_token)
        except Exception as e:
            print("Error sending reset email:", e)

    conn.close()

    # Always the same response
    return {
        "message": "If an account exists for that email, we’ve sent a reset link. Check your inbox (and Spam/Junk)."
    }


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(token: str):
    """
    Render a minimal HTML page for setting a new password.
    Validates that the token exists & is not expired.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, reset_password_expires_at
        FROM users
        WHERE reset_password_token = %s
        """,
        (token,),
    )
    row = cur.fetchone()

    # Basic invalid / expired handling
    if row is None:
        conn.close()
        html_error = """
        <html>
          <body style="background:#050509; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                       min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px;">
            <div style="background:#111118;border-radius:16px;padding:24px 22px;max-width:380px;
                        border:1px solid #27272f;color:#f5f5f5;text-align:center;">
              <h1 style="font-size:20px;margin:0 0 8px;">Reset link not valid</h1>
              <p style="font-size:13px;color:#e5e7eb;margin:0 0 12px;">
                This password reset link is invalid or has already been used.
              </p>
              <p style="font-size:12px;color:#9ca3af;margin:0 0 10px;">
                Request a new reset link from the “Forgot password” page.
              </p>
              <a href="/login"
                 style="display:inline-block;margin-top:12px;padding:8px 14px;border-radius:999px;
                        background:#e50914;color:#ffffff;text-decoration:none;font-size:13px;font-weight:500;">
                Go to login
              </a>
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html_error, status_code=400)

    expires_at = row["reset_password_expires_at"]

    if expires_at is None or expires_at.replace(tzinfo=None) < datetime.utcnow():
        conn.close()
        html_expired = """
        <html>
          <body style="background:#050509; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                       min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px;">
            <div style="background:#111118;border-radius:16px;padding:24px 22px;max-width:380px;
                        border:1px solid #27272f;color:#f5f5f5;text-align:center;">
              <h1 style="font-size:20px;margin:0 0 8px;">Reset link expired</h1>
              <p style="font-size:13px;color:#e5e7eb;margin:0 0 12px;">
                This password reset link has expired.
              </p>
              <p style="font-size:12px;color:#9ca3af;margin:0 0 10px;">
                Go back to “Forgot password” and request a fresh link.
              </p>
              <a href="/login"
                 style="display:inline-block;margin-top:12px;padding:8px 14px;border-radius:999px;
                        background:#e50914;color:#ffffff;text-decoration:none;font-size:13px;font-weight:500;">
                Back to login
              </a>
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html_expired, status_code=400)

    conn.close()

    # If we’re here, token is valid → render reset form
    html_form = f"""
    <html>
      <body style="background:#050509; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                   min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px;">
        <div style="background:#111118;border-radius:16px;padding:24px 22px;max-width:380px;
                    border:1px solid #27272f;color:#f5f5f5;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.16em;color:#9ca3af;margin-bottom:6px;">
            Deepmode
          </div>
          <h1 style="font-size:20px;margin:0 0 6px;">Set a new password</h1>
          <p style="font-size:13px;color:#e5e7eb;margin:0 0 14px;">
            Choose a strong password you won’t reuse on other sites.
          </p>

          <div style="margin-bottom:8px;">
            <label style="display:block;font-size:11px;color:#9ca3af;margin-bottom:4px;">New password</label>
            <input id="password" type="password"
                   style="width:100%;padding:7px 8px;border-radius:8px;border:1px solid #27272f;
                          background:#050509;color:#f5f5f5;font-size:13px;" />
          </div>

          <div style="margin-bottom:10px;">
            <label style="display:block;font-size:11px;color:#9ca3af;margin-bottom:4px;">Confirm password</label>
            <input id="confirm" type="password"
                   style="width:100%;padding:7px 8px;border-radius:8px;border:1px solid #27272f;
                          background:#050509;color:#f5f5f5;font-size:13px;" />
          </div>

          <button onclick="submitReset()"
                  style="width:100%;margin-top:6px;padding:8px 10px;border-radius:999px;border:none;
                         background:#e50914;color:#ffffff;font-size:13px;font-weight:500;cursor:pointer;">
            Update password
          </button>

          <div id="msg" style="margin-top:10px;font-size:12px;color:#bbf7d0;display:none;"></div>
          <div id="err" style="margin-top:10px;font-size:12px;color:#fecaca;display:none;"></div>

          <p style="font-size:11px;color:#6b7280;margin-top:12px;text-align:center;">
            After resetting, you’ll be redirected back to login.
          </p>
        </div>

        <script>
          async function submitReset() {{
            const msg = document.getElementById("msg");
            const err = document.getElementById("err");
            msg.style.display = "none";
            err.style.display = "none";

            const p = document.getElementById("password").value;
            const c = document.getElementById("confirm").value;

            if (!p || !c) {{
              err.textContent = "Please enter and confirm your new password.";
              err.style.display = "block";
              return;
            }}
            if (p !== c) {{
              err.textContent = "Passwords don’t match.";
              err.style.display = "block";
              return;
            }}
            if (p.length < 8) {{
              err.textContent = "Password should be at least 8 characters.";
              err.style.display = "block";
              return;
            }}

            try {{
              const res = await fetch("/auth/reset-password", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                  token: "{token}",
                  new_password: p
                }})
              }});

              if (!res.ok) {{
                const data = await res.json().catch(() => ({{}}));
                err.textContent = data.detail || "Could not reset password. Try again.";
                err.style.display = "block";
                return;
              }}

              msg.textContent = "Password updated. You can now log in with your new password.";
              msg.style.display = "block";
              setTimeout(() => {{
                window.location.href = "/login";
              }}, 1800);
            }} catch (e) {{
              console.error(e);
              err.textContent = "Network error. Try again.";
              err.style.display = "block";
            }}
          }}
        </script>
      </body>
    </html>
    """

    return HTMLResponse(content=html_form, status_code=200)



@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """
    Consume a valid reset token, set a new password, send confirmation email.
    """
    conn = get_conn()
    cur = conn.cursor()

    token = payload.token
    new_password = payload.new_password

    if len(new_password) < 8:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    cur.execute(
        """
        SELECT id, email, reset_password_expires_at
        FROM users
        WHERE reset_password_token = %s
        """,
        (token,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    expires_at = row["reset_password_expires_at"]
    if expires_at is None or expires_at.replace(tzinfo=None) < datetime.utcnow():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link has expired. Please request a new one.",
        )

    user_id = row["id"]
    email = row["email"]

    # Update password + clear reset fields
    pw_hash = hash_password(new_password)
    cur.execute(
        """
        UPDATE users
        SET password_hash = %s,
            reset_password_token = NULL,
            reset_password_expires_at = NULL
        WHERE id = %s
        """,
        (pw_hash, user_id),
    )
    conn.commit()
    conn.close()

    # --------- SEND CONFIRMATION EMAIL ----------
    subject = "Your Deepmode password was changed"
    body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                padding:24px;background:#020617;color:#f9fafb;">
      <h1 style="margin:0 0 10px;font-size:20px;">Password updated</h1>
      <p style="font-size:14px;line-height:1.6;margin:0 0 12px;">
        This is a quick confirmation that the password for your Deepmode account
        (<span style="color:#e5e7eb;">{email}</span>) was just changed.
      </p>
      <p style="font-size:13px;line-height:1.6;margin:0 0 10px;color:#9ca3af;">
        If this was you, you’re all set. You can now log in with your new password.
      </p>
      <p style="font-size:13px;line-height:1.6;margin:0 0 14px;color:#f97373;">
        If this wasn’t you, change your password again immediately and secure your email account.
      </p>
      <a href="https://deepmode.app/login"
         style="display:inline-block;padding:8px 14px;border-radius:999px;background:#e50914;
                color:#ffffff;text-decoration:none;font-size:13px;font-weight:500;">
        Go to login
      </a>
    </div>
    """

    try:
        send_email_html(email, subject, body)
    except Exception as e:
        # Do NOT rollback the password change, just log the email issue
        print("Error sending password reset confirmation email:", e)

    return {"message": "Password updated successfully."}


# ---------- Dependency ----------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Extract current user from Bearer token.
    Used as a dependency in protected routes.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s ", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    return {
        "id": row["id"],
        "email": row["email"],
        "is_pro": bool(row["is_pro"]),
        "is_verified": bool(row.get("is_verified", False)),
    }
