from datetime import timedelta
from pathlib import Path
import os

from flask import Flask, request
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
app.config["SESSION_TYPE"] = os.getenv("SESSION_TYPE", "filesystem")
app.config["SESSION_FILE_DIR"] = os.getenv(
    "SESSION_FILE_DIR",
    str(Path(app.instance_path) / "flask_session") if hasattr(app, "instance_path") else str(Path(__file__).parent / "flask_session"),
)
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Ensure the session folder exists
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

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


def limit_key_ip_plus_route():
    """Use IP + concrete request path for stricter endpoint-specific throttling."""
    return f"{get_remote_address()}:{request.path}"


limiter = Limiter(
    key_func=get_remote_address,
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
    limit_key_func=limit_key_ip_plus_route,
    exempt_limiter=lambda: not rate_limit_enabled(),
    get_courses=get_courses,
    get_course_lessons=get_course_lessons,
    is_access_code_valid_for_lesson=is_access_code_valid_for_lesson,
    find_lesson_by_access_code=find_lesson_by_access_code,
    load_lesson_content=load_lesson_content,
    get_course_skeleton_keys=get_course_skeleton_keys,
)


@app.after_request
def disable_html_cache(response):
    """Prevent stale browser-cached HTML during content editing."""
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


register_security_middleware(app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
