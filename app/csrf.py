"""CSRF token generation and validation."""
import os
import secrets
from typing import Optional
from fastapi import Request, HTTPException

CSRF_SECRET = os.environ.get("SECRET_KEY", os.environ.get("CSRF_SECRET", ""))
if not CSRF_SECRET:
    # Dev fallback - tokens are signed but not cryptographically strong
    CSRF_SECRET = "dev_csrf_secret_change_in_production"


def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return secrets.token_urlsafe(32)


def get_csrf_token(request: Request) -> Optional[str]:
    """Get CSRF token from request (header or form body)."""
    # Check header first (for JS fetch)
    token = request.headers.get("X-CSRF-Token")
    if token:
        return token
    # Check form data (for traditional forms)
    try:
        body = request.scope.get("_csrf_body_cache")
        if body is None:
            # Don't consume the body - just peek if possible
            return None
        if isinstance(body, bytes):
            from urllib.parse import parse_qs
            params = parse_qs(body.decode("utf-8"))
            return params.get("csrf_token", [None])[0]
    except Exception:
        pass
    return None


def validate_csrf(request: Request) -> None:
    """Validate CSRF token from request against session cookie."""
    expected = request.cookies.get("csrf_token")
    provided = get_csrf_token(request)
    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise HTTPException(403, "Invalid or missing CSRF token")
