from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from app.database import get_conn
from app.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

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


# ---------- Routes ----------

@router.post("/register")
def register(payload: RegisterRequest):
    """
    Create a new user.
    """
    conn = get_conn()
    cur = conn.cursor()

    email = payload.email.lower()

    # Check if email already exists
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    now = datetime.utcnow().isoformat()
    pw_hash = hash_password(payload.password)

    cur.execute(
        """
        INSERT INTO users (email, password_hash, is_pro, created_at, updated_at)
        VALUES (?, ?, 0, ?, ?)
        """,
        (email, pw_hash, now, now),
    )
    conn.commit()
    conn.close()

    return {"message": "Account created. Welcome to Deepmode! Take back your focus, one block at a time."}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """
    Log in with email + password (JSON body).
    Return a JWT access token.
    """
    conn = get_conn()
    cur = conn.cursor()

    email = payload.email.lower()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(
        {
            "sub": row["email"],
            "user_id": row["id"],
            "is_pro": bool(row["is_pro"]),
        }
    )

    return TokenResponse(access_token=token)


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
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
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
    }
