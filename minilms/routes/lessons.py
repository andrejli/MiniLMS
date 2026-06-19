"""Lesson access, public lesson, and hex-code lesson routes."""

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from minilms import session_manager


def _get_courses():
    return current_app.config["MINILMS_GET_COURSES"]()


def _get_course_lessons(course_slug, course_title):
    return current_app.config["MINILMS_GET_COURSE_LESSONS"](course_slug, course_title)


def _is_access_code_valid_for_lesson(course_slug, lesson_id, access_code):
    return current_app.config["MINILMS_IS_ACCESS_CODE_VALID_FOR_LESSON"](
        course_slug,
        lesson_id,
        access_code,
    )


def _find_lesson_by_access_code(access_code):
    return current_app.config["MINILMS_FIND_LESSON_BY_ACCESS_CODE"](access_code)


def _load_lesson_content(course_slug, lesson_id):
    return current_app.config["MINILMS_LOAD_LESSON_CONTENT"](course_slug, lesson_id)


def create_lesson_blueprint(
    limiter,
    access_post_limit,
    limit_key_func,
    exempt_limiter,
):
    lesson_bp = Blueprint("lessons", __name__)

    @lesson_bp.route("/courses/<slug>/lessons/<int:lesson_id>/access", methods=["GET", "POST"])
    @limiter.limit(
        access_post_limit,
        methods=["POST"],
        key_func=limit_key_func,
        exempt_when=exempt_limiter,
    )
    def lesson_access(slug, lesson_id):
        course = next((course for course in _get_courses() if course["slug"] == slug), None)
        if not course:
            return "Course not found", 404

        lessons = _get_course_lessons(course["slug"], course["title"])
        lesson = next((item for item in lessons if item["id"] == lesson_id), None)
        if not lesson:
            return "Lesson not found", 404

        if not lesson.get("hex"):
            return redirect(
                url_for(
                    "lessons.lesson_page",
                    slug=slug,
                    lesson_id=lesson_id,
                )
            )

        error_message = ""
        if request.method == "POST":
            access_code = request.form.get("access_code", "").strip().lower()
            if _is_access_code_valid_for_lesson(slug, lesson_id, access_code):
                # Retrieve course lessons to get all IDs (needed for skeleton unlock)
                lesson_files = _get_course_lessons(slug, course["title"])
                lesson_ids = [item["id"] for item in lesson_files]
                
                # Check if it is a skeleton key
                skeleton_keys = current_app.config["MINILMS_GET_COURSE_SKELETON_KEYS"](slug)
                if access_code in skeleton_keys:
                    session_manager.grant_skeleton_unlock(slug, lesson_ids)
                else:
                    session_manager.grant_unlock(slug, lesson_id)
                
                return redirect(
                    url_for(
                        "lessons.lesson_page",
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

    @lesson_bp.get("/courses/<slug>/lessons/<int:lesson_id>")
    def lesson_page(slug, lesson_id):
        course = next((course for course in _get_courses() if course["slug"] == slug), None)
        if not course:
            return "Course not found", 404

        lessons = _get_course_lessons(course["slug"], course["title"])
        lesson = next((item for item in lessons if item["id"] == lesson_id), None)

        # Check if the lesson requires access
        has_hex = False
        lesson_title = f"Lesson {lesson_id}"
        if lesson:
            has_hex = bool(lesson.get("hex"))
            lesson_title = lesson["title"]
        else:
            # File is missing. Check access.json to see if it was restricted
            from pathlib import Path
            from minilms.access_control import get_lesson_access_codes
            access_file = Path(__file__).parents[2] / "access.json"
            has_hex = bool(get_lesson_access_codes(access_file, slug, lesson_id))

        if has_hex:
            if not session_manager.is_unlocked(slug, lesson_id):
                return redirect(url_for("lessons.lesson_access", slug=slug, lesson_id=lesson_id))
        else:
            if not lesson:
                return "Lesson not found", 404

        content_html = _load_lesson_content(slug, lesson_id)
        return render_template(
            "lesson_page.html",
            entry={
                "course_slug": slug,
                "course_title": course["title"],
                "lesson_title": lesson_title,
                "lesson_id": lesson_id,
            },
            content_html=content_html,
            back_link=url_for("courses.course_detail", slug=slug),
            back_label=f"Back to {course['title']}",
        )

    @lesson_bp.get("/lessons/<hex_id>.html")
    def legacy_lesson_page(hex_id):
        hex_id = hex_id.lower()
        lesson_match = None

        target_course_slug = request.args.get("slug", "").strip().lower()
        target_lesson_id = request.args.get("lesson_id", "").strip()
        if target_course_slug and target_lesson_id:
            try:
                target_lesson_id = int(target_lesson_id)
                if _is_access_code_valid_for_lesson(target_course_slug, target_lesson_id, hex_id):
                    lesson_match = (target_course_slug, target_lesson_id)
            except ValueError:
                lesson_match = None

        if not lesson_match:
            lesson_match = _find_lesson_by_access_code(hex_id)
        if not lesson_match:
            return (
                render_template(
                    "lesson_page.html",
                    entry={
                        "course_title": "Access denied",
                        "lesson_title": "Wrong code",
                    },
                    back_link=url_for("core.home"),
                    back_label="Back to courses",
                ),
                404,
            )

        course_slug, lesson_id = lesson_match
        course = next((item for item in _get_courses() if item["slug"] == course_slug), None)
        
        # Grant session unlock (same as POST handler)
        lesson_files = _get_course_lessons(course_slug, course["title"] if course else "")
        lesson_ids = [item["id"] for item in lesson_files]
        skeleton_keys = current_app.config["MINILMS_GET_COURSE_SKELETON_KEYS"](course_slug)
        
        if hex_id in skeleton_keys:
            session_manager.grant_skeleton_unlock(course_slug, lesson_ids)
        else:
            session_manager.grant_unlock(course_slug, lesson_id)

        current_app.logger.warning("legacy hex-code URL accessed: %s. Redirecting to session-based URL.", hex_id)

        return redirect(
            url_for("lessons.lesson_page", slug=course_slug, lesson_id=lesson_id),
            code=308,
        )

    return lesson_bp
