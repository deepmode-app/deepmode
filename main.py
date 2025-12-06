import os
from pathlib import Path
import zipfile

from dotenv import load_dotenv

# ---------- Load .env BEFORE importing app.database ----------

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse

from app.routes import sessions, billing, auth, marketing_router, projects
from app.database import init_db
from app.jobs.email_jobs import router as jobs_router  # /jobs/... endpoints

# ---------- Init DB + app ----------

init_db()

app = FastAPI(title="Deepmode")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Routers ----------

app.include_router(auth.router)
app.include_router(sessions.router, prefix="/sessions")
app.include_router(billing.router, tags=["billing"])
app.include_router(projects.router)  # /projects/ endpoints
app.include_router(jobs_router)  # /jobs/daily-streak-digest, /jobs/weekly-summary-digest
app.include_router(marketing_router)




# ---------- Static paths ----------

STATIC_DIR = BASE_DIR / "app" / "static"
EXTENSION_DIR = STATIC_DIR / "deepmode-extension"
TEMP_ZIP = STATIC_DIR / "deepmode-extension-download.zip"


# ---------- Page routes ----------

@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/settings/profile", include_in_schema=False)
def profile_settings():
    """
    Profile & Settings page - authenticated users only.
    """
    return FileResponse(STATIC_DIR / "profile.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/signup", include_in_schema=False)
def signup_page():
    return FileResponse(STATIC_DIR / "signup.html")


@app.get("/install", include_in_schema=False)
def install_page():
    return FileResponse(STATIC_DIR / "install.html")


# ---------- Static file serving ----------

@app.get("/static/{file_path:path}", include_in_schema=False)
def serve_static(file_path: str):
    """
    Serve static files (images, CSS, etc.) from app/static/
    """
    file_path_obj = STATIC_DIR / file_path
    if not file_path_obj.exists() or not file_path_obj.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path_obj)




# ---------- Extension ZIP download ----------

@app.get("/download-extension", include_in_schema=False)
def download_extension():
    """
    Package the deepmode-extension folder into a zip on the fly
    and send it as a download.
    """
    if not EXTENSION_DIR.exists():
        raise HTTPException(
            status_code=500,
            detail="Extension folder not found on server.",
        )

    # Clean up any old zip
    if TEMP_ZIP.exists():
        TEMP_ZIP.unlink()

    # Build fresh zip from static/deepmode-extension
    with zipfile.ZipFile(TEMP_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in EXTENSION_DIR.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(EXTENSION_DIR)
                zf.write(path, arcname)

    return FileResponse(
        TEMP_ZIP,
        filename="deepmode-extension.zip",
        media_type="application/zip",
    )
