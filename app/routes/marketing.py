# app/routes/marketing.py

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

# Router for all public / marketing pages
router = APIRouter(tags=["marketing"])

# Figure out where /app/static lives from this file's location
# __file__ = app/routes/marketing.py
APP_DIR = Path(__file__).resolve().parents[1]   # -> app
STATIC_DIR = APP_DIR / "static"


def _static_file(name: str) -> FileResponse:
    """
    Small helper to safely serve a static HTML file from app/static.
    Raises 404 if the file is missing instead of a 500.
    """
    path = STATIC_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path)


@router.get("/pricing", include_in_schema=False)
def pricing_page():
    """
    Redirect to landing page pricing section.
    """
    return RedirectResponse("/#pricing", status_code=302)


@router.get("/terms", include_in_schema=False)
def terms_page():
    """
    Terms of Service.
    """
    return _static_file("terms.html")


@router.get("/privacy", include_in_schema=False)
def privacy_page():
    """
    Privacy Policy.
    """
    return _static_file("privacy.html")


@router.get("/contact", include_in_schema=False)
def contact_page():
    """
    Simple contact info page.
    """
    return _static_file("contact.html")


@router.get("/faq", include_in_schema=False)
def faq_page():
    """
    Frequently asked questions.
    """
    return _static_file("faq.html")


@router.get("/streak", include_in_schema=False)
def streak_page():
    """
    Work tracker page - authentication handled by frontend JavaScript.
    """
    return _static_file("streak.html")


@router.get("/reports", include_in_schema=False)
def reports_page():
    """
    Reports and analytics page.
    """
    return _static_file("reports.html")


@router.get("/about", include_in_schema=False)
def about_page():
    """
    About Deepmode page.
    """
    return _static_file("about.html")


@router.get("/support", include_in_schema=False)
def support_page():
    """
    Support page.
    """
    return _static_file("support.html")