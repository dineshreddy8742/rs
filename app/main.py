"""Main application entry point for AuraRise.

This module initializes the FastAPI application, configures routers, middleware,
and handles application startup and shutdown events. It serves as the central
coordination point for the entire application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.database.connector import SupabaseConnectionManager
from app.api.routers.resume import resume_router
from app.api.routers.token_usage import router as token_usage_router
from app.api.routers.auth import auth_router
from app.api.routers.feedback import feedback_router
from app.web.core import core_web_router
from app.web.base_router import WebRouter
from app.web.dashboard import web_router as dashboard_web_router

web_router = WebRouter()
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    # Startup: Initialize Supabase connection
    try:
        connection_manager = SupabaseConnectionManager()
        app.state.supabase = connection_manager
        print(f"Started {settings.PROJECT_NAME} v{settings.VERSION}")
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    
    yield
    
    # Shutdown: Clean up resources
    print("Shutting down and cleaning up.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    summary="AI-backed resume generator for OpenRouter/DeepSeek",
    description="Scalable resume optimization for students.",
    lifespan=lifespan,
    docs_url=None,
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Custom exception handler for HTTP exceptions.

    Renders the 404.html template for 404 errors.
    For other HTTP errors, renders a basic error page or returns JSON for API routes.

    Args:
        request: The incoming request
        exc: The HTTP exception that was raised

    Returns:
    -------
        An appropriate response based on the request type and error
    """
    if exc.status_code == 404:
        # Check if this is an API request or a web page request
        if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code=404, content={"detail": "Resource not found"}
            )
        # For web requests, render our custom 404 page
        return templates.TemplateResponse(
            request, "404.html", {"request": request}, status_code=404
        )

    # For API routes, return JSON error
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": str(exc.detail)}
        )

    # For other errors on web routes, show an error page with details
    error_title = "Page Not Found" if exc.status_code == 404 else "Error Occurred"
    if exc.status_code == 403: error_title = "Access Denied"
    if exc.status_code == 401: error_title = "Authentication Required"
    
    return templates.TemplateResponse(
        request,
        "404.html",
        {
            "request": request, 
            "status_code": exc.status_code, 
            "error_title": error_title,
            "detail": str(exc.detail)
        },
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom exception handler for request validation errors.

    Args:
        request: The incoming request
        exc: The validation error that was raised

    Returns:
    -------
        JSON response for API routes or template response for web routes
    """
    # For API routes, return JSON error
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    # For web routes, show an error page with validation details
    return templates.TemplateResponse(
        request,
        "404.html",
        {
            "request": request,
            "status_code": 422,
            "error_title": "Validation Error",
            "detail": "Please check your input data. Some required fields might be missing or in the wrong format.",
        },
        status_code=422,
    )


@app.middleware("http")
async def add_response_headers(request: Request, call_next):
    """Middleware to add response headers and handle flashed messages.

    Args:
        request: The incoming request
        call_next: The next middleware or route handler

    Returns:
    -------
        The response with added security headers
    """
    response = await call_next(request)

    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    return response


# Add middleware and static file mounts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/templates", StaticFiles(directory="app/templates"), name="templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Serve custom Swagger UI HTML for API documentation.

    Returns:
    -------
        HTMLResponse: Custom Swagger UI HTML

    Raises:
    ------
        FileNotFoundError: If the custom Swagger template is not found
    """
    try:
        with open("app/templates/custom_swagger.html") as f:
            template = f.read()

        return HTMLResponse(
            template.replace("{{ title }}", "AuraRise API Documentation").replace(
                "{{ openapi_url }}", "/openapi.json"
            )
        )
    except FileNotFoundError:
        return HTMLResponse(
            content="Custom Swagger template not found", status_code=500
        )
    except Exception as e:
        return HTMLResponse(
            content=f"Error loading documentation: {str(e)}", status_code=500
        )


@app.get("/health", tags=["Health"], summary="Health Check")
async def health_check():
    """Health check endpoint for monitoring and container orchestration.

    Returns:
    -------
        JSONResponse: Status information about the application.
    """
    return JSONResponse(
        content={"status": "healthy", "version": app.version, "service": "aurarise"}
    )


# Include routers - These must come BEFORE the catch-all route
app.include_router(resume_router)
app.include_router(token_usage_router)
app.include_router(auth_router)
app.include_router(feedback_router)
app.include_router(core_web_router)
app.include_router(dashboard_web_router)
app.include_router(web_router)

# Explicit root route to serve the HTML landing page (overrides FastAPI default JSON)
@app.get("/", include_in_schema=False)
async def root_page(request: Request):
    """Serve the HTML landing page."""
    return templates.TemplateResponse(request, "index.html", {"request": request})


# Catch-all for not found pages - IMPORTANT: This must come AFTER including all routers
@app.get("/{path:path}", include_in_schema=False)
async def catch_all(request: Request, path: str):
    """Catch-all route handler for undefined paths.

    This must be defined AFTER all other routes to avoid intercepting valid routes.

    Args:
        request: The incoming request
        path: The path that was not matched by any other route

    Returns:
    -------
        Template response with 404 page
    """
    # Skip handling for paths that should be handled by other middleware/routers
    if path.startswith(("api/", "static/", "templates/", "docs")):
        # Let the normal routing handle these paths
        raise StarletteHTTPException(status_code=404)

    # For truly non-existent routes, render the 404 page
    return templates.TemplateResponse(request, "404.html", {"request": request}, status_code=404)
