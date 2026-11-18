"""FastAPI entry point for the local DocuGuard dashboard."""

import os
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analyzer import analyze_repository
from .auth import auth_is_required, auth_configuration, hosted_auth_guard
from .schemas import AnalysisResponse, DeletionStatus, RepositoryAnalysisRequest, SecurityStatus
from .server_ai import is_loopback_peer, validate_ai_output

logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocuGuard",
    description="Evidence-backed checks for documentation drift in Python repositories.",
    version="0.1.0",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def enforce_local_scope_and_security_headers(request, call_next):
    """Fail closed if the API is accidentally reached from another machine."""
    peer = request.client.host if request.client else None
    if not is_loopback_peer(peer):
        return JSONResponse(status_code=403, content={"detail": "DocuGuard accepts local connections only."})
    # Browser state changes must come from the exact local dashboard origin.
    # Requests without Origin are rejected as well, making the browser boundary explicit.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        allowed = {
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://localhost:5174", "http://127.0.0.1:5174",
            "http://localhost:5175", "http://127.0.0.1:5175",
        }
        # The packaged app serves its own UI and API on one loopback port.
        # Permit that exact origin without opening the API to other websites.
        allowed.add(str(request.base_url).rstrip("/"))
        if origin not in allowed:
            return JSONResponse(status_code=403, content={"detail": "This request origin is not allowed."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self' https://*.supabase.co wss://*.supabase.co; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.middleware("http")
async def protect_repository_analysis(request, call_next):
    """Validate hosted sessions on the API before repository work starts."""
    return await hosted_auth_guard(request, call_next)


@app.get("/health")
def health() -> dict[str, str]:
    """A simple endpoint the dashboard can use to check server readiness."""
    return {"status": "ok"}


@app.get("/security/status", response_model=SecurityStatus)
def security_status() -> SecurityStatus:
    """Expose only safe policy facts; never reveal model endpoint or secrets."""
    return SecurityStatus(
        network_scope="Loopback clients only",
        repository_access="Read-only Git inspection",
        persistence="No repository content is stored by the API",
        api_keys_in_browser=False,
        remote_ai_allowed=False,
        ai_enabled=os.getenv("DOCUGUARD_AI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
        hosted_auth_configured=auth_configuration() is not None,
        hosted_auth_required=auth_is_required(),
        transport="HTTP over local loopback",
        note="Loopback limits network reach; it is not TLS encryption. Use an approved TLS proxy before any remote deployment.",
    )


@app.post("/privacy/deletion-request", response_model=DeletionStatus)
def deletion_request() -> DeletionStatus:
    """Acknowledge deletion without collecting identity or saving a request."""
    return DeletionStatus(
        message="DocuGuard stores no repository results or account data. Clear the page to remove its in-memory inputs and findings.",
    )


@app.post("/analyze/repository", response_model=AnalysisResponse)
def analyze(request: RepositoryAnalysisRequest) -> AnalysisResponse:
    """Analyze changed Python and Markdown files between two Git refs."""
    try:
        return validate_ai_output(analyze_repository(request.repository_path, request.base_ref, request.head_ref))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        # Keep internal paths, model responses, and exception text out of HTTP errors.
        logger.error("Repository analysis failed: %s", type(error).__name__)
        raise HTTPException(
            status_code=500,
            detail="DocuGuard could not complete the local analysis. Check the repository and try again.",
        ) from error


# In a release build, serve the compiled dashboard from the same loopback-only
# process as the API. This makes the normal launch a single local application.
dashboard_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dashboard_dist.is_dir():
    app.mount("/", StaticFiles(directory=dashboard_dist, html=True), name="dashboard")
