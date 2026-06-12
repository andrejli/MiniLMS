"""Course discovery and detail routes."""

from flask import Blueprint, current_app, render_template

course_bp = Blueprint("courses", __name__)


def _get_courses():
    return current_app.config["MINILMS_GET_COURSES"]()


def _get_course_lessons(course_slug, course_title):
    return current_app.config["MINILMS_GET_COURSE_LESSONS"](course_slug, course_title)


@course_bp.get("/courses/<slug>")
def course_detail(slug):
    course = next((course for course in _get_courses() if course["slug"] == slug), None)
    if not course:
        return "Course not found", 404

    lessons = _get_course_lessons(course["slug"], course["title"])
    return render_template(
        "course_detail.html",
        course=course,
        lessons=lessons,
        lessons_count=len(lessons),
    )
