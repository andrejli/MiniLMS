from datetime import timedelta
from pathlib import Path
import os

from cachelib import FileSystemCache
from flask import Flask, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session
from werkzeug.middleware.proxy_fix import ProxyFix

from minilms import access_control
from minilms import content_service
from minilms.routes import register_blueprints
from minilms.security_headers import env_flag, register_security_middleware

app = Flask(__name__)

# Configure session handling
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")

session_dir = os.getenv(
    "SESSION_FILE_DIR",
    str(Path(app.instance_path) / "flask_session") if hasattr(app, "instance_path") else str(Path(__file__).parent / "flask_session"),
)
os.makedirs(session_dir, exist_ok=True)

app.config["SESSION_TYPE"] = os.getenv("SESSION_TYPE", "cachelib")
app.config["SESSION_CACHELIB"] = FileSystemCache(
    cache_dir=session_dir,
    threshold=500,
    mode=0o600,
)
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Initialize Session
Session(app)

CONTENT_ROOT = Path(__file__).with_name("content") / "lessons"
ACCESS_CODES_FILE = Path(__file__).with_name("access.json")

RATE_LIMIT_ENABLED = env_flag("RATE_LIMIT_ENABLED", default=True)
RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
RATE_LIMIT_GLOBAL_HOURLY = os.getenv("RATE_LIMIT_GLOBAL_HOURLY", "120/hour")
RATE_LIMIT_GLOBAL_MINUTE = os.getenv("RATE_LIMIT_GLOBAL_MINUTE", "30/minute")
RATE_LIMIT_ACCESS_POST_MINUTE = os.getenv("RATE_LIMIT_ACCESS_POST_MINUTE", "5/minute")
RATE_LIMIT_ACCESS_POST_HOURLY = os.getenv("RATE_LIMIT_ACCESS_POST_HOURLY", "20/hour")

# Trust one proxy hop by default so client IP identity is accurate behind a reverse proxy.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)


def _content_root():
    """Get the current content root path (supports monkeypatching in tests)."""
    return CONTENT_ROOT


def _access_codes_file():
    """Get the current access file path (supports monkeypatching in tests)."""
    return ACCESS_CODES_FILE


def rate_limit_enabled():
    """Read limiter toggle at request time to support environment-driven control."""
    return env_flag("RATE_LIMIT_ENABLED", default=RATE_LIMIT_ENABLED)


def _session_or_ip():
    """Return stable session ID, falling back to client IP."""
    try:
        sid = session.sid
        if sid:
            # Touch the session so flask-session's save_session persists it
            # with a cookie. Without this, an empty/unmodified session won't
            # get a Set-Cookie header, each request creates a new SID, and
            # session-based rate limiting never accumulates a counter.
            session.setdefault("_sd", True)
            return f"sess:{sid}"
    except (RuntimeError, AttributeError, TypeError, KeyError):
        pass
    return get_remote_address()


def limit_key():
    """Global rate limit key: session ID when available, else IP."""
    return _session_or_ip()


def limit_key_sid_plus_route():
    """Per-route rate limit key: session ID + path, else IP + path."""
    return f"{_session_or_ip()}:{request.path}"


limiter = Limiter(
    key_func=limit_key,
    app=app,
    default_limits=[RATE_LIMIT_GLOBAL_HOURLY, RATE_LIMIT_GLOBAL_MINUTE],
    default_limits_exempt_when=lambda: not rate_limit_enabled(),
    storage_uri=RATE_LIMIT_STORAGE_URI,
    headers_enabled=True,
)


def is_hex_access_code(value):
    """Compatibility wrapper for legacy imports/tests."""
    return access_control.is_hex_access_code(value)


def load_access_codes():
    """Compatibility wrapper for access control lookup."""
    return access_control.load_access_codes(_access_codes_file())


def get_course_skeleton_keys(course_slug):
    """Compatibility wrapper for course-level skeleton keys."""
    return access_control.get_course_skeleton_keys(_access_codes_file(), course_slug)


def get_lesson_access_codes(course_slug, lesson_id):
    """Compatibility wrapper for lesson-level access codes."""
    return access_control.get_lesson_access_codes(_access_codes_file(), course_slug, lesson_id)


def is_access_code_valid_for_lesson(course_slug, lesson_id, access_code):
    """Compatibility wrapper for lesson unlock validation."""
    return access_control.is_access_code_valid_for_lesson(
        _access_codes_file(),
        course_slug,
        lesson_id,
        access_code,
    )


def find_lesson_by_access_code(access_code):
    """Compatibility wrapper for global code lookup."""
    return access_control.find_lesson_by_access_code(_access_codes_file(), access_code)


def list_lesson_files(course_slug):
    """Compatibility wrapper for lesson-file discovery."""
    return content_service.list_lesson_files(_content_root(), course_slug)


def get_courses():
    """Compatibility wrapper for course discovery."""
    return content_service.get_courses(_content_root())


def get_course_lessons(course_slug, course_title):
    """Compatibility wrapper for template-facing lesson metadata."""
    return content_service.get_course_lessons(
        _content_root(),
        get_lesson_access_codes,
        course_slug,
        course_title,
    )


def find_course_by_label(label):
    """Compatibility wrapper for course title/slug matching."""
    return content_service.find_course_by_label(_content_root(), label)


def load_lesson_content(course_slug, lesson_id):
    """Compatibility wrapper for markdown rendering."""
    return content_service.load_lesson_content(_content_root(), course_slug, lesson_id)


register_blueprints(
    app=app,
    limiter=limiter,
    access_post_limit=f"{RATE_LIMIT_ACCESS_POST_MINUTE};{RATE_LIMIT_ACCESS_POST_HOURLY}",
    limit_key_func=limit_key_sid_plus_route,
    exempt_limiter=lambda: not rate_limit_enabled(),
)


CACHE_HTML_MAX_AGE_SECS = int(os.getenv("CACHE_HTML_MAX_AGE", "3600"))

@app.after_request
def set_html_cache(response):
    """Allow browser caching of HTML for a configurable window.

    Set CACHE_HTML_MAX_AGE=0 (or via env) to restore the previous
    no-store behaviour during content editing. Default is 3600 (1 hour).
    """
    if response.mimetype == "text/html" and response.status_code == 200:
        response.headers["Cache-Control"] = f"private, max-age={CACHE_HTML_MAX_AGE_SECS}"
        response.headers["Pragma"] = "cache"
    return response


@app.after_request
def remove_server_header(response):
    response.headers.pop("Server", None)
    return response


register_security_middleware(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
