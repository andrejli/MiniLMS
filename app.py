"""MiniLMS Flask application.

This module implements a file-backed learning platform where:
- Course/lesson content is loaded from Markdown files under content/lessons.
- Lesson access control is configured in access.json.
- Restricted lessons can be unlocked with lesson-specific keys or course-level
    skeleton keys.
"""

from pathlib import Path
import json
import re

import markdown
from flask import Flask, redirect, render_template, request, url_for
from markupsafe import Markup

app = Flask(__name__)

CONTENT_ROOT = Path(__file__).with_name("content") / "lessons"
ACCESS_CODES_FILE = Path(__file__).with_name("access.json")
HEX_ACCESS_CODE_RE = re.compile(r"^[0-9a-f]{6,64}$")


@app.after_request
def disable_html_cache(response):
    """Prevent stale browser-cached HTML during content editing."""
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def is_hex_access_code(value):
    """Return True when a value matches the accepted hex key format."""
    return bool(HEX_ACCESS_CODE_RE.fullmatch(value))


def load_access_codes():
    """Load and normalize access control data from access.json.

    Expected JSON schema:
    {
      "course-slug": {
        "skeleton_keys": ["hex...", ...],
        "0": ["hex...", ...],
        "1": ["hex...", ...]
      }
    }

    Returns:
        dict: Normalized structure in the form:
            {
              "course-slug": {
                "skeleton_keys": [...],
                "lessons": {0: [...], 1: [...]}
              }
            }
    """
    if not ACCESS_CODES_FILE.exists():
        return {}
    try:
        # Invalid or unreadable JSON should not crash the app.
        payload = json.loads(ACCESS_CODES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}

    normalized = {}
    for course_slug, course_codes in payload.items():
        if not isinstance(course_codes, dict):
            continue
        lesson_codes = {}
        skeleton_keys = []
        for lesson_id, codes in course_codes.items():
            if lesson_id == "skeleton_keys":
                # skeleton_keys unlock every restricted lesson in the course.
                if not isinstance(codes, list):
                    continue
                for code in codes:
                    if not isinstance(code, str):
                        continue
                    normalized_code = code.strip().lower()
                    # Only keep valid hex keys.
                    if normalized_code and is_hex_access_code(normalized_code):
                        skeleton_keys.append(normalized_code)
                continue

            # Standard lesson mapping: "lesson_id": ["hex1", "hex2", ...].
            if not isinstance(codes, list):
                continue
            try:
                lesson_id_int = int(lesson_id)
            except (TypeError, ValueError):
                continue

            normalized_codes = []
            for code in codes:
                if not isinstance(code, str):
                    continue
                normalized_code = code.strip().lower()
                if normalized_code and is_hex_access_code(normalized_code):
                    normalized_codes.append(normalized_code)
            if normalized_codes:
                lesson_codes[lesson_id_int] = normalized_codes

        if lesson_codes or skeleton_keys:
            normalized[str(course_slug)] = {
                "skeleton_keys": skeleton_keys,
                "lessons": lesson_codes,
            }
    return normalized


def get_course_skeleton_keys(course_slug):
    """Return the list of skeleton keys for a course slug."""
    return load_access_codes().get(course_slug, {}).get("skeleton_keys", [])


def get_lesson_access_codes(course_slug, lesson_id):
    """Return all valid codes for one lesson.

    Includes lesson-specific codes and, when the lesson is restricted,
    course-level skeleton keys.
    """
    course_access = load_access_codes().get(course_slug, {})
    lesson_codes = course_access.get("lessons", {}).get(lesson_id, [])
    # Only explicitly configured lessons are considered restricted.
    if not lesson_codes:
        return []
    skeleton_keys = course_access.get("skeleton_keys", [])
    return lesson_codes + [code for code in skeleton_keys if code not in lesson_codes]


def is_access_code_valid_for_lesson(course_slug, lesson_id, access_code):
    """Check whether a provided code can unlock a specific lesson."""
    return access_code in get_lesson_access_codes(course_slug, lesson_id)


def find_lesson_by_access_code(access_code):
    """Resolve a code to a lesson when explicit lesson context is missing.

    For skeleton keys, the first restricted lesson (by lesson id) is used as a
    deterministic fallback target.
    """
    for course_slug, course_access in load_access_codes().items():
        lesson_codes = course_access.get("lessons", {})
        skeleton_keys = course_access.get("skeleton_keys", [])
        for lesson_id, codes in lesson_codes.items():
            if access_code in codes:
                return course_slug, lesson_id
        if access_code in skeleton_keys:
            # Pick a stable lesson when a skeleton key is used without context.
            for lesson_id in sorted(lesson_codes.keys()):
                return course_slug, lesson_id
    return None


def list_lesson_files(course_slug):
    """Discover and normalize lesson markdown files for one course.

    Conventions:
    - Summary.md maps to lesson id 0.
    - lesson-<n>.md and lesson<n>.md map to lesson id <n>.
    - session-<n>.md and session<n>.md map to lesson id <n>.
    """
    course_dir = CONTENT_ROOT / course_slug
    if not course_dir.exists():
        return []
    lessons = []
    for path in course_dir.glob("*.md"):
        stem = path.stem.strip()
        if stem.lower() == "summary":
            lessons.append({"id": 0, "path": path, "is_summary": True})
            continue
        match = re.fullmatch(r"(?:lesson|session)-?(\d+)", stem.lower())
        if not match:
            continue
        lesson_id = int(match.group(1))
        lessons.append({"id": lesson_id, "path": path, "is_summary": False})
    return sorted(lessons, key=lambda item: item["id"])


def get_courses():
    """Build the course catalog from folder names under content/lessons."""
    if not CONTENT_ROOT.exists():
        return []
    courses = []
    for course_dir in sorted([p for p in CONTENT_ROOT.iterdir() if p.is_dir()]):
        slug = course_dir.name
        title = slug.replace("-", " ").title()
        lessons = list_lesson_files(slug)
        courses.append(
            {
                "slug": slug,
                "title": title,
                "category": "Courses",
                "summary": "Lesson content loaded from the content folder.",
                "level": "Self-paced",
                "lessons": len(lessons),
                "lesson_ids": [item["id"] for item in lessons],
            }
        )
    return courses


def get_course_lessons(course_slug, course_title):
    """Build lesson metadata used by templates for a single course."""
    lesson_files = list_lesson_files(course_slug)
    return [
        {
            "id": item["id"],
            "title": (
                "Summary"
                if item["is_summary"]
                else f"Lesson {item['id']}: {course_title}"
            ),
            "hex": get_lesson_access_codes(course_slug, item["id"]),
        }
        for item in lesson_files
    ]


def find_course_by_label(label):
    """Find a course by title or slug (case-insensitive).

    This helper is kept for convenience and future feature expansion.
    """
    if not label:
        return None
    normalized = label.strip().lower()
    for course in get_courses():
        if normalized in (course["title"].lower(), course["slug"].lower()):
            return course
    return None


def load_lesson_content(course_slug, lesson_id):
    """Load lesson markdown and convert it to HTML markup."""
    lesson_files = list_lesson_files(course_slug)
    match = next((item for item in lesson_files if item["id"] == lesson_id), None)
    if not match:
        return None
    text = match["path"].read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    return Markup(html)


@app.get("/")
def home():
    """Render the course catalog landing page."""
    return render_template("index.html", courses=get_courses())


@app.get("/courses/<slug>")
def course_detail(slug):
    """Render a single course page with lesson list."""
    course = next((c for c in get_courses() if c["slug"] == slug), None)
    if not course:
        return "Course not found", 404
    lessons = get_course_lessons(course["slug"], course["title"])
    return render_template(
        "course_detail.html",
        course=course,
        lessons=lessons,
        lessons_count=len(lessons),
    )


@app.route(
    "/courses/<slug>/lessons/<int:lesson_id>/access",
    methods=["GET", "POST"],
)
def lesson_access(slug, lesson_id):
    """Render and process the access-code form for restricted lessons."""
    course = next((c for c in get_courses() if c["slug"] == slug), None)
    if not course:
        return "Course not found", 404
    lessons = get_course_lessons(course["slug"], course["title"])
    lesson = next((item for item in lessons if item["id"] == lesson_id), None)
    if not lesson:
        return "Lesson not found", 404

    # Public lessons bypass access-gate form entirely.
    if not lesson.get("hex"):
        return redirect(url_for("public_lesson_page", slug=slug, lesson_id=lesson_id))

    error_message = ""
    if request.method == "POST":
        access_code = request.form.get("access_code", "").strip().lower()
        if is_access_code_valid_for_lesson(slug, lesson_id, access_code):
            # Keep course/lesson context in the URL for skeleton key resolution.
            return redirect(
                url_for(
                    "lesson_page",
                    hex_id=access_code,
                    slug=slug,
                    lesson_id=lesson_id,
                )
            )
        error_message = "Wrong access code."
    return render_template(
        "lesson_access.html",
        course=course,
        lesson=lesson,
        error_message=error_message,
    )


@app.get("/courses/<slug>/lessons/<int:lesson_id>")
def public_lesson_page(slug, lesson_id):
    """Render a lesson directly when no access key is required."""
    course = next((c for c in get_courses() if c["slug"] == slug), None)
    if not course:
        return "Course not found", 404

    lessons = get_course_lessons(course["slug"], course["title"])
    lesson = next((item for item in lessons if item["id"] == lesson_id), None)
    if not lesson:
        return "Lesson not found", 404

    # Restricted lessons must use the access flow.
    if lesson.get("hex"):
        return redirect(url_for("lesson_access", slug=slug, lesson_id=lesson_id))

    content_html = load_lesson_content(slug, lesson_id)
    return render_template(
        "lesson_page.html",
        entry={
            "course_slug": slug,
            "course_title": course["title"],
            "lesson_title": lesson["title"],
            "lesson_id": lesson_id,
        },
        content_html=content_html,
        back_link=url_for("course_detail", slug=slug),
        back_label=f"Back to {course['title']}",
    )


@app.get("/lessons/<hex_id>.html")
def lesson_page(hex_id):
    """Render lesson content when a valid hex code is provided.

    Resolution strategy:
    1) Try explicit context from query params (slug + lesson_id).
    2) Fall back to global lookup by access code.
    """
    hex_id = hex_id.lower()
    courses = get_courses()
    lesson_match = None

    # Context-aware lookup avoids ambiguity for skeleton keys.
    target_course_slug = request.args.get("slug", "").strip().lower()
    target_lesson_id = request.args.get("lesson_id", "").strip()
    if target_course_slug and target_lesson_id:
        try:
            target_lesson_id = int(target_lesson_id)
            if is_access_code_valid_for_lesson(
                target_course_slug,
                target_lesson_id,
                hex_id,
            ):
                lesson_match = (target_course_slug, target_lesson_id)
        except ValueError:
            lesson_match = None

    if not lesson_match:
        # Generic fallback for direct URL access.
        lesson_match = find_lesson_by_access_code(hex_id)
    if not lesson_match:
        return render_template(
            "lesson_page.html",
            entry={
                "course_title": "Access denied",
                "lesson_title": "Wrong code",
            },
            back_link=url_for("home"),
            back_label="Back to courses",
        ), 404

    # Build display metadata for the resolved lesson.
    course_slug, lesson_id = lesson_match
    course = next((c for c in courses if c["slug"] == course_slug), None)
    lesson_title = f"Lesson {lesson_id}"
    if course:
        lessons = get_course_lessons(course_slug, course["title"])
        lesson = next((item for item in lessons if item["id"] == lesson_id), None)
        if lesson:
            lesson_title = lesson["title"]

    entry = {
        "course_slug": course_slug,
        "course_title": course["title"] if course else "Restricted lesson",
        "lesson_title": lesson_title,
        "lesson_id": lesson_id,
    }

    # Prefer course-specific back navigation when possible.
    back_link = url_for("home")
    back_label = "Back to courses"
    if course:
        back_link = url_for("course_detail", slug=course["slug"])
        back_label = f"Back to {course['title']}"
    content_html = load_lesson_content(entry["course_slug"], entry["lesson_id"])
    return render_template(
        "lesson_page.html",
        entry=entry,
        content_html=content_html,
        back_link=back_link,
        back_label=back_label,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
