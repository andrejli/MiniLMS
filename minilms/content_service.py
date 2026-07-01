"""Filesystem-backed course and lesson discovery/rendering."""

from pathlib import Path
import re
from functools import lru_cache

import markdown
from markupsafe import Markup

LESSON_FILENAME_RE = re.compile(r"(?:lesson|session)-?(\d+)")


@lru_cache(maxsize=64)
def _list_lesson_files_cached(course_dir_str, dir_mtime):
    """Discover and normalize lesson markdown files, caching result based on mtime."""
    course_dir = Path(course_dir_str)
    lessons = []
    for path in course_dir.glob("*.md"):
        stem = path.stem.strip()
        if stem.lower() == "summary":
            lessons.append({"id": 0, "path": path, "is_summary": True})
            continue

        match = LESSON_FILENAME_RE.fullmatch(stem.lower())
        if not match:
            continue
        lesson_id = int(match.group(1))
        lessons.append({"id": lesson_id, "path": path, "is_summary": False})

    return sorted(lessons, key=lambda item: item["id"])


def list_lesson_files(content_root, course_slug):
    """Discover and normalize lesson markdown files for one course."""
    course_dir = Path(content_root) / course_slug
    if not course_dir.exists():
        return []
    try:
        dir_mtime = course_dir.stat().st_mtime
    except OSError:
        dir_mtime = 0.0
    return _list_lesson_files_cached(str(course_dir), dir_mtime)


def get_courses(content_root):
    """Build the course catalog from folder names under content/lessons."""
    root = Path(content_root)
    if not root.exists():
        return []

    courses = []
    for course_dir in sorted([path for path in root.iterdir() if path.is_dir()]):
        slug = course_dir.name
        title = slug.replace("-", " ").title()
        lessons = list_lesson_files(root, slug)
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


def get_course_lessons(content_root, access_codes_for_lesson, course_slug, course_title):
    """Build lesson metadata used by templates for a single course."""
    lesson_files = list_lesson_files(content_root, course_slug)
    return [
        {
            "id": item["id"],
            "title": (
                "Summary"
                if item["is_summary"]
                else f"Lesson {item['id']}: {course_title}"
            ),
            "hex": access_codes_for_lesson(course_slug, item["id"]),
        }
        for item in lesson_files
    ]


def find_course_by_label(content_root, label):
    """Find a course by title or slug (case-insensitive)."""
    if not label:
        return None
    normalized = label.strip().lower()
    for course in get_courses(content_root):
        if normalized in (course["title"].lower(), course["slug"].lower()):
            return course
    return None


@lru_cache(maxsize=128)
def _render_markdown(path_str, mtime):
    """Render markdown file to HTML, cached based on mtime."""
    text = Path(path_str).read_text(encoding="utf-8")
    return markdown.markdown(text, extensions=["fenced_code", "tables"])


def load_lesson_content(content_root, course_slug, lesson_id):
    """Load lesson markdown and convert it to HTML markup."""
    lesson_files = list_lesson_files(content_root, course_slug)
    match = next((item for item in lesson_files if item["id"] == lesson_id), None)
    if not match:
        return None

    path = match["path"]
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    html = _render_markdown(str(path), mtime)
    return Markup(html)
