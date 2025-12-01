# app/routes/projects.py

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from urllib.parse import unquote

from app.database import get_conn
from app.routes.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------- Pydantic Models ----------

class ProjectInfo(BaseModel):
    name: str
    session_count: int


class RenameProjectRequest(BaseModel):
    old_name: str
    new_name: str


# ---------- GET /projects/ ----------

@router.get("/", response_model=list[ProjectInfo])
def list_projects(current_user: dict = Depends(get_current_user)):
    """
    Return a list of distinct project names with session counts for the current user.
    Only includes projects with non-empty project_name.
    """
    user_id = current_user["id"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            project_name AS name,
            COUNT(*)::INT AS session_count
        FROM sessions
        WHERE user_id = %s
          AND project_name IS NOT NULL
          AND project_name != ''
        GROUP BY project_name
        ORDER BY LOWER(project_name)
        """,
        (user_id,),
    )

    rows = cur.fetchall()
    conn.close()

    return [
        ProjectInfo(name=row["name"], session_count=row["session_count"])
        for row in rows
    ]


# ---------- PATCH /projects/rename ----------

@router.patch("/rename")
def rename_project(
    payload: RenameProjectRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Rename a project by updating all sessions with the old project name to the new name.
    """
    user_id = current_user["id"]

    old_name = payload.old_name.strip()
    new_name = payload.new_name.strip()

    if not old_name or not new_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both old_name and new_name must be non-empty after trimming.",
        )

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE sessions
        SET project_name = %s
        WHERE user_id = %s
          AND project_name = %s
        """,
        (new_name, user_id, old_name),
    )

    updated_count = cur.rowcount
    conn.commit()
    conn.close()

    return {"updated": updated_count}


# ---------- DELETE /projects/{project_name} ----------

@router.delete("/{project_name}")
def delete_project(
    project_name: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Clear the project_name label from all sessions for this user.
    Does NOT delete the sessions, only removes the project label.
    """
    user_id = current_user["id"]

    # URL decode the project name
    decoded_name = unquote(project_name)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE sessions
        SET project_name = NULL
        WHERE user_id = %s
          AND project_name = %s
        """,
        (user_id, decoded_name),
    )

    cleared_count = cur.rowcount
    conn.commit()
    conn.close()

    return {"cleared": cleared_count}
