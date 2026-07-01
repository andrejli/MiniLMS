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
):
    """Register all route blueprints."""
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
