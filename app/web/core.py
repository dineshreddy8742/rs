"""Core web module for primary web routes.

This module implements core web interface routes for the application,
handling primary pages like the landing page, about page, and other
central web content.
"""

from pathlib import Path

from fastapi import Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.web.base_router import WebRouter
from app.core.security import require_admin, require_login_redirect

# Setup templates
templates_path = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

core_web_router = WebRouter()


@core_web_router.get(
    "/",
    summary="Homepage",
    response_description="Welcome to DailSmart AI",
    response_class=HTMLResponse,
)
async def home(
    request: Request,
):
    """Render the homepage."""
    return templates.TemplateResponse(
        name="index.html",
        context={"request": request},
    )


@core_web_router.get(
    "/about",
    summary="About Us",
    response_description="Learn more about DailSmart AI",
    response_class=HTMLResponse,
)
async def about(
    request: Request,
):
    """Render the about page."""
    return templates.TemplateResponse(
        name="about.html",
        context={"request": request},
    )


@core_web_router.get(
    "/contribution",
    summary="Contribution",
    response_description="Get involved with DailSmart AI development",
    response_class=HTMLResponse,
)
async def contribution(
    request: Request,
):
    """Render the contribution page."""
    return templates.TemplateResponse(
        name="contribution.html",
        context={"request": request},
    )


@core_web_router.get(
    "/create",
    summary="Create Resume",
    response_description="Resume creation page",
    response_class=HTMLResponse,
)
async def create_resume(
    request: Request,
):
    """Render the resume creation page."""
    redirect = require_login_redirect(request)
    if redirect: return redirect
    return templates.TemplateResponse(
        name="create.html",
        context={"request": request},
    )

@core_web_router.get(
    "/build",
    summary="Build Resume from Scratch",
    response_description="Resume builder page",
    response_class=HTMLResponse,
)
async def build_resume(
    request: Request,
):
    """Render the resume builder page."""
    redirect = require_login_redirect(request)
    if redirect: return redirect
    return templates.TemplateResponse(
        name="build_resume.html",
        context={"request": request},
    )

@core_web_router.get(
    "/cover-letter",
    summary="Cover Letter Generator",
    response_description="Cover letter generation page",
    response_class=HTMLResponse,
)
async def cover_letter_page(
    request: Request,
):
    """Render the cover letter generator page."""
    redirect = require_login_redirect(request)
    if redirect: return redirect
    return templates.TemplateResponse(
        name="cover_letter.html",
        context={"request": request},
    )

@core_web_router.get(
    "/login",
    summary="Login Page",
    response_description="Login page",
    response_class=HTMLResponse,
)
async def login_page(
    request: Request,
):
    """Render the login page."""
    return templates.TemplateResponse(
        name="login.html",
        context={"request": request},
    )

@core_web_router.get(
    "/admin",
    summary="Admin Dashboard",
    response_description="Admin dashboard",
    response_class=HTMLResponse,
)
async def admin_page(
    request: Request,
    _ = Depends(require_admin)
):
    """Render the admin dashboard."""
    # Note: require_admin is a dependency, so it will raise 403 if not admin
    return templates.TemplateResponse(
        name="admin.html",
        context={"request": request},
    )

@core_web_router.get(
    "/admin/colleges/{college_id}",
    summary="College Detail View",
    response_description="College details with enrolled students",
    response_class=HTMLResponse,
)
async def college_detail(
    request: Request,
    college_id: str,
    _ = Depends(require_admin)
):
    """Render college detail page showing enrolled students."""
    return templates.TemplateResponse(
        name="college_detail.html",
        context={"request": request, "college_id": college_id},
    )

@core_web_router.get(
    "/profile",
    summary="User Profile",
    response_description="Profile page",
    response_class=HTMLResponse,
)
async def profile_page(
    request: Request,
):
    """Render the user profile page."""
    redirect = require_login_redirect(request)
    if redirect: return redirect
    return templates.TemplateResponse(
        name="profile.html",
        context={"request": request},
    )
