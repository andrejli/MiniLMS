"""Core blueprint routes and global HTTP error handlers."""

from flask import Blueprint, current_app, render_template, request, url_for
from flask_limiter.util import get_remote_address
from markupsafe import Markup

core_bp = Blueprint("core", __name__)


def _get_courses():
    return current_app.config["MINILMS_GET_COURSES"]()


@core_bp.get("/")
def home():
    return render_template("index.html", courses=_get_courses())


@core_bp.app_errorhandler(404)
def handle_not_found(_error):
    """Render a custom 404 page without exposing framework internals."""
    return (
        render_template(
            "error_404.html",
            title="Page not found",
        ),
        404,
    )


@core_bp.app_errorhandler(500)
def handle_internal_server_error(error):
    """Render a generic 500 page while logging internal error details."""
    current_app.logger.exception(
        "internal_server_error path=%s method=%s",
        request.path,
        request.method,
        exc_info=error,
    )
    return (
        render_template(
            "error_500.html",
            title="Something went wrong",
        ),
        500,
    )


@core_bp.app_errorhandler(429)
def handle_rate_limit_exceeded(error):
    """Return a user-safe 429 response with retry guidance."""
    retry_after = None
    if hasattr(error, "get_response"):
        base_response = error.get_response()
        retry_after = base_response.headers.get("Retry-After")
    if not retry_after and hasattr(error, "retry_after"):
        retry_after = str(error.retry_after)
    if retry_after in {"", "None", None}:
        retry_after = None

    retry_guidance = "Please try again in 60 seconds."
    if retry_after:
        retry_guidance = f"Please try again in {retry_after} seconds."

    current_app.logger.warning(
        "rate_limited route=%s method=%s ip=%s policy=%s decision=deny",
        request.path,
        request.method,
        get_remote_address(),
        getattr(error, "description", "unknown"),
    )

    response = render_template(
        "lesson_page.html",
        entry={
            "course_title": "Too many requests",
            "lesson_title": "Rate limit reached",
        },
        content_html=Markup(f"<p>Too many requests. {retry_guidance}</p>"),
        back_link=url_for("core.home"),
        back_label="Back to courses",
    )
    headers = {}
    if retry_after:
        headers["Retry-After"] = retry_after
    return response, 429, headers
