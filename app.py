from pathlib import Path

import markdown
from flask import Flask, redirect, render_template, request, url_for
from markupsafe import Markup

app = Flask(__name__)

CONTENT_ROOT = Path(__file__).with_name("content") / "lessons"

LESSON_HEX_ROUTES = {
    ("python-basics", 0): "a15555",
    ("python-basics", 1): "47a463c27f4",
}


def list_lesson_files(course_slug):
    course_dir = CONTENT_ROOT / course_slug
    if not course_dir.exists():
        return []
    lessons = []
    for path in course_dir.glob("*.md"):
        stem = path.stem.strip()
        if stem.lower() == "summary":
            lessons.append({"id": 0, "path": path, "is_summary": True})
            continue
        if not stem.lower().startswith("lesson-"):
            continue
        try:
            lesson_id = int(stem.split("lesson-")[1])
        except (IndexError, ValueError):
            continue
        lessons.append({"id": lesson_id, "path": path, "is_summary": False})
    return sorted(lessons, key=lambda item: item["id"])


def get_courses():
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
    lesson_files = list_lesson_files(course_slug)
    return [
        {
            "id": item["id"],
            "title": "Summary" if item["is_summary"] else f"Lesson {item['id']}: {course_title}",
            "hex": LESSON_HEX_ROUTES.get((course_slug, item["id"])),
        }
        for item in lesson_files
    ]


def find_course_by_label(label):
    if not label:
        return None
    normalized = label.strip().lower()
    for course in get_courses():
        if normalized in (course["title"].lower(), course["slug"].lower()):
            return course
    return None


def load_lesson_content(course_slug, lesson_id):
    lesson_files = list_lesson_files(course_slug)
    match = next((item for item in lesson_files if item["id"] == lesson_id), None)
    if not match:
        return None
    text = match["path"].read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    return Markup(html)


@app.get("/")
def home():
    return render_template("index.html", courses=get_courses())


@app.get("/courses/<slug>")
def course_detail(slug):
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

@app.route("/courses/<slug>/lessons/<int:lesson_id>/access", methods=["GET", "POST"])
def lesson_access(slug, lesson_id):
    course = next((c for c in get_courses() if c["slug"] == slug), None)
    if not course:
        return "Course not found", 404
    lessons = get_course_lessons(course["slug"], course["title"])
    lesson = next((item for item in lessons if item["id"] == lesson_id), None)
    if not lesson:
        return "Lesson not found", 404
    error_message = ""
    if request.method == "POST":
        access_code = request.form.get("access_code", "").strip()
        if access_code == lesson.get("hex"):
            return redirect(url_for("lesson_page", hex_id=access_code))
        error_message = "Wrong access code."
    return render_template(
        "lesson_access.html",
        course=course,
        lesson=lesson,
        error_message=error_message,
    )


@app.get("/lessons/<hex_id>.html")
def lesson_page(hex_id):
    courses = get_courses()
    entry = next(
        (
            {
                "course_slug": course_slug,
                "course_title": course["title"],
                "lesson_title": f"Lesson {lesson_id}: {course['title']}",
                "lesson_id": lesson_id,
            }
            for (course_slug, lesson_id), value in LESSON_HEX_ROUTES.items()
            if value == hex_id
            for course in courses
            if course["slug"] == course_slug
        ),
        None,
    )
    if not entry:
        return render_template(
            "lesson_page.html",
            entry={
                "course_title": "Access denied",
                "lesson_title": "Wrong code",
            },
            back_link=url_for("home"),
            back_label="Back to courses",
        ), 404
    course = next((c for c in courses if c["slug"] == entry["course_slug"]), None)
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
