"""Security headers and HTTPS enforcement hooks."""

import os

from flask import redirect, request


def env_flag(name, default=False):
    """Parse boolean environment flags from common string values."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_force_https():
    """Enable HTTPS enforcement by default in production-like environments.
    Returns False by default so that Tor (.onion) deployments work out of
    the box without needing to set FORCE_HTTPS=false. Set FORCE_HTTPS=true
    explicitly to enable the redirect when running behind a TLS proxy.
    """
    return False


def add_security_headers(response):
    """Attach baseline security headers to every response."""
    if not env_flag("SECURITY_HEADERS_ENABLED", default=True):
        return response

    csp = os.getenv(
        "CONTENT_SECURITY_POLICY",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'",
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = os.getenv("X_FRAME_OPTIONS", "SAMEORIGIN")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = os.getenv(
        "REFERRER_POLICY",
        "strict-origin-when-cross-origin",
    )
    response.headers["X-XSS-Protection"] = "1; mode=block"

    is_https = request.is_secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    if is_https:
        response.headers["Strict-Transport-Security"] = os.getenv(
            "HSTS_HEADER",
            "max-age=31536000; includeSubDomains",
        )
    return response


def enforce_https_redirect():
    """Redirect plain HTTP requests to HTTPS when enabled."""
    force_https = env_flag("FORCE_HTTPS", default=default_force_https())
    if not force_https:
        return None

    is_https = request.is_secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    if is_https:
        return None

    secure_url = request.url.replace("http://", "https://", 1)
    return redirect(secure_url, code=308)


def register_security_middleware(app):
    """Register security-related request/response hooks."""
    app.before_request(enforce_https_redirect)
    app.after_request(add_security_headers)
