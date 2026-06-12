"""Blueprint registration for MiniLMS routes."""

from minilms.routes.core import core_bp
from minilms.routes.courses import course_bp
from minilms.routes.lessons import create_lesson_blueprint


def register_blueprints(
    app,
    limiter,
    access_post_limit,
    limit_key_func,
    exempt_limiter,
    get_courses,
    get_course_lessons,
    is_access_code_valid_for_lesson,
    find_lesson_by_access_code,
    load_lesson_content,
):
    """Register all route blueprints and service bindings."""
    app.config["MINILMS_GET_COURSES"] = get_courses
    app.config["MINILMS_GET_COURSE_LESSONS"] = get_course_lessons
    app.config["MINILMS_IS_ACCESS_CODE_VALID_FOR_LESSON"] = is_access_code_valid_for_lesson
    app.config["MINILMS_FIND_LESSON_BY_ACCESS_CODE"] = find_lesson_by_access_code
    app.config["MINILMS_LOAD_LESSON_CONTENT"] = load_lesson_content

    app.register_blueprint(core_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(
        create_lesson_blueprint(
            limiter=limiter,
            access_post_limit=access_post_limit,
            limit_key_func=limit_key_func,
            exempt_limiter=exempt_limiter,
        )
    )
