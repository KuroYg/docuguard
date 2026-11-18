"""Fail-closed Supabase token verification for protected API routes.

This prototype delegates passwords, email verification, refresh-token rotation,
and lockout throttling to Supabase Auth. The API independently validates each
bearer token with Supabase before reading a requested repository.
"""

import asyncio
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
VERIFY_TIMEOUT_SECONDS = 4


def auth_configuration() -> tuple[str, str] | None:
    """Return public project settings only when both are set and well-formed.

    Supabase's URL is public, as is its anon/publishable key. Validate them
    before making network requests so an incomplete setup never looks enabled.
    """
    url = os.getenv("DOCUGUARD_SUPABASE_URL", "").rstrip("/")
    anon_key = os.getenv("DOCUGUARD_SUPABASE_ANON_KEY", "")
    if not url or not anon_key:
        return None
    parsed_url = urlsplit(url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
        or parsed_url.path
        or any(character.isspace() for character in anon_key)
        or anon_key in {"replace-with-public-anon-key", "your-anon-key"}
        or "your-project" in parsed_url.hostname
    ):
        return None
    return url, anon_key


def auth_is_required() -> bool:
    return os.getenv("DOCUGUARD_AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}


def protected_route_needs_auth(path: str) -> bool:
    """Once a provider is configured, repository reads always require identity."""
    partial_or_invalid_setup = bool(
        os.getenv("DOCUGUARD_SUPABASE_URL", "").strip()
        or os.getenv("DOCUGUARD_SUPABASE_ANON_KEY", "").strip()
    ) and auth_configuration() is None
    return path.startswith("/analyze/repository") and (
        auth_is_required() or auth_configuration() is not None or partial_or_invalid_setup
    )


def bearer_token_from_header(header: str) -> str | None:
    """Accept only an explicit nonempty bearer credential; reject other schemes."""
    scheme, separator, token = header.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip() or len(token.strip()) > 8192:
        return None
    return token.strip()


def _verify_with_supabase(token: str, config: tuple[str, str]) -> dict | None:
    """Ask Supabase Auth to validate token signature, expiry, and current user."""
    project_url, anon_key = config
    request = Request(
        f"{project_url}/auth/v1/user",
        headers={"apikey": anon_key, "Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=VERIFY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(32_768).decode("utf-8"))
        return payload if isinstance(payload, dict) and payload.get("id") else None
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as error:
        # Invalid credentials are normal; only log the exception class, never token or response.
        logger.info("Hosted token verification failed: %s", type(error).__name__)
        return None


def _active_customer_profile(user_id: str, token: str, config: tuple[str, str]) -> bool | None:
    """Check this verified user's own profile through Supabase row-level security.

    `True` means an active account, `False` means the account is absent/disabled,
    and `None` means the identity provider or database could not be checked.
    The caller fails closed for both non-active and unavailable states.
    """
    project_url, anon_key = config
    safe_user_id = quote(user_id, safe="")
    request = Request(
        f"{project_url}/rest/v1/customer_profiles?user_id=eq.{safe_user_id}&select=account_status",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=VERIFY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(8_192).decode("utf-8"))
        return isinstance(payload, list) and len(payload) == 1 and payload[0].get("account_status") == "active"
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as error:
        logger.info("Hosted account authorization check failed: %s", type(error).__name__)
        return None


def authorized_role(user: dict) -> str | None:
    """Allow ordinary customers and trusted admins, rejecting unknown role claims.

    Supabase `app_metadata` is managed by trusted server operators; user-editable
    `user_metadata` is deliberately ignored. DocuGuard currently has no admin-only
    product routes, so both allowed roles have the same product permissions.
    """
    app_metadata = user.get("app_metadata")
    role = app_metadata.get("role", "user") if isinstance(app_metadata, dict) else "user"
    return role if role in {"user", "admin"} else None


async def verify_bearer_token(token: str) -> dict | None:
    """Verify a token without blocking FastAPI's event loop during the network call."""
    config = auth_configuration()
    if not config or len(token) > 8192:
        return None
    return await asyncio.to_thread(_verify_with_supabase, token, config)


async def hosted_auth_guard(request: FastAPIRequest, call_next):
    """Protect repository analysis when hosted auth is enabled; fail closed on setup errors."""
    if request.url.path.startswith("/analyze/repository"):
        config = auth_configuration()
        if not protected_route_needs_auth(request.url.path):
            return await call_next(request)
        if not config:
            return JSONResponse(
                status_code=503,
                content={"detail": "Hosted authentication settings are incomplete or invalid. Check the API environment and restart it."},
            )
        token = bearer_token_from_header(request.headers.get("authorization", ""))
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Sign in to analyze a repository."}, headers={"WWW-Authenticate": "Bearer"})
        user = await verify_bearer_token(token)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Your session is invalid or expired. Sign in again."}, headers={"WWW-Authenticate": "Bearer"})
        role = authorized_role(user)
        if role is None:
            return JSONResponse(status_code=403, content={"detail": "This account is not authorized to analyze repositories."})
        profile_status = await asyncio.to_thread(_active_customer_profile, user["id"], token, config)
        if profile_status is None:
            return JSONResponse(status_code=503, content={"detail": "Account authorization could not be checked. Try again shortly."})
        if not profile_status:
            return JSONResponse(status_code=403, content={"detail": "This account is inactive or not provisioned."})
        # Attach only provider-verified claims. Authorization decisions must never
        # trust user-editable user_metadata; privileged roles use app_metadata.
        request.state.auth_user_id = user["id"]
        request.state.auth_role = role
    return await call_next(request)
