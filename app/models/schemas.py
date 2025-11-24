from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ---------- USER MODELS ----------

class UserBase(BaseModel):
    email: str
    plan: str  # "free" or "paid"


class UserCreate(UserBase):
    password: str  # for now; later you can switch to magic links


class UserRead(UserBase):
    id: int
    created_at: datetime


# ---------- SESSION MODELS ----------

class SessionCreate(BaseModel):
    task: str
    category: str  # "coding", "writing", etc.
    planned_duration_minutes: int


class SessionRead(BaseModel):
    id: int
    user_id: int
    task: str
    category: Optional[str] = None
    planned_duration_minutes: int
    start_time: datetime
    end_time: Optional[datetime] = None
    actual_duration_minutes: Optional[int] = None
    discipline_score: Optional[float] = None
    status: Optional[str] = None          # 'running', 'completed', 'partial', 'abandoned', 'auto_closed'
    duration_seconds: Optional[int] = None
    project_name: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        orm_mode = True


class SessionUpdate(BaseModel):
    """
    Partial update model for sessions.
    Only fields that are set will be updated.
    """
    task: Optional[str] = None
    category: Optional[str] = None
    project_name: Optional[str] = None
    notes: Optional[str] = None


class SessionSummary(BaseModel):
    today_minutes: int
    all_time_minutes: int
    total_sessions: int
    completed_sessions: int


# ---------- DISTRACTION EVENT MODELS ----------

class DistractionEventCreate(BaseModel):
    session_id: int
    url: str


class DistractionEventRead(BaseModel):
    id: int
    session_id: int
    user_id: int
    url: str
    created_at: datetime
