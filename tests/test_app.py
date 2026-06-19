from pathlib import Path
import json
import sys

import pytest
from flask import url_for
from werkzeug.exceptions import TooManyRequests
from werkzeug.routing import BuildError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch):
    """Keep existing tests deterministic unless a test explicitly enables throttling."""
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")


def setup_content(tmp_path):
    content_root = tmp_path / "lessons"
    course_dir = content_root / "python-basics"
    course_dir.mkdir(parents=True)
    (course_dir / "Summary.md").write_text(
        "# Summary\n\nOverview text.",
        encoding="utf-8",
    )
    (course_dir / "lesson-1.md").write_text(
        "# Lesson 1\n\n**Bold** text.",
        encoding="utf-8",
    )

    free_course_dir = content_root / "free-course"
    free_course_dir.mkdir(parents=True)
    (free_course_dir / "Summary.md").write_text(
        "# Free Summary\n\nLorem ipsum.",
        encoding="utf-8",
    )
    (free_course_dir / "lesson-1.md").write_text(
        "# Free Lesson\n\nNo key required.",
        encoding="utf-8",
    )
    return content_root


def setup_access_codes(tmp_path, payload=None):
    access_codes = payload or {"python-basics": {"1": ["47a463c27f4"]}}
    access_file = tmp_path / "access.json"
    access_file.write_text(json.dumps(access_codes), encoding="utf-8")
    return access_file


def test_course_discovery_from_content(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)

    courses = app.get_courses()

    assert len(courses) == 2
    courses_by_slug = {course["slug"]: course for course in courses}
    assert courses_by_slug["python-basics"]["title"] == "Python Basics"
    assert courses_by_slug["python-basics"]["lessons"] == 2
    assert set(courses_by_slug["python-basics"]["lesson_ids"]) == {0, 1}
    assert courses_by_slug["free-course"]["title"] == "Free Course"
    assert courses_by_slug["free-course"]["lessons"] == 2
    assert set(courses_by_slug["free-course"]["lesson_ids"]) == {0, 1}


def test_session_filename_is_discovered_as_lesson(tmp_path, monkeypatch):
    content_root = tmp_path / "lessons"
    course_dir = content_root / "it_sec"
    course_dir.mkdir(parents=True)
    (course_dir / "session1.md").write_text(
        "# Session 1\n\nIntro.",
        encoding="utf-8",
    )

    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)

    courses = app.get_courses()
    courses_by_slug = {course["slug"]: course for course in courses}

    assert "it_sec" in courses_by_slug
    assert courses_by_slug["it_sec"]["lessons"] == 1
    assert courses_by_slug["it_sec"]["lesson_ids"] == [1]


def test_access_flow_and_rendered_lesson(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "47a463c27f4"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/courses/python-basics/lessons/1"

    lesson_response = client.get("/courses/python-basics/lessons/1")
    assert lesson_response.status_code == 200
    assert b"<strong>Bold</strong>" in lesson_response.data


def test_wrong_code_returns_404(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.get("/lessons/badcode.html")
    assert response.status_code == 404
    assert b"Wrong code" in response.data


def test_free_course_lessons_do_not_require_access_key(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    course_response = client.get("/courses/free-course")
    assert course_response.status_code == 200
    assert b"OPEN LESSON" in course_response.data

    lesson_response = client.get("/courses/free-course/lessons/1")
    assert lesson_response.status_code == 200
    assert b"No key required." in lesson_response.data


def test_protected_lessons_still_require_access_key(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.get("/courses/python-basics/lessons/1")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/courses/python-basics/lessons/1/access"
    )


def test_summary_lesson_can_be_restricted_via_access_json(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(
        tmp_path,
        payload={"python-basics": {"0": ["a15555"]}},
    )
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.get("/courses/python-basics/lessons/0")
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/courses/python-basics/lessons/0/access"
    )

    unlocked = client.post(
        "/courses/python-basics/lessons/0/access",
        data={"access_code": "a15555"},
    )
    assert unlocked.status_code == 302
    assert unlocked.headers["Location"] == "/courses/python-basics/lessons/0"


def test_any_code_in_lesson_code_list_unlocks_lesson(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(
        tmp_path,
        payload={"python-basics": {"1": ["47a463c27f4", "abc123"]}},
    )
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "abc123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/courses/python-basics/lessons/1"


def test_skeleton_key_unlocks_multiple_lessons(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(
        tmp_path,
        payload={
            "python-basics": {
                "skeleton_keys": ["c0ffee"],
                "0": ["a15555"],
                "1": ["47a463c27f4"],
            }
        },
    )
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    lesson0 = client.post(
        "/courses/python-basics/lessons/0/access",
        data={"access_code": "c0ffee"},
    )
    assert lesson0.status_code == 302
    assert lesson0.headers["Location"] == "/courses/python-basics/lessons/0"

    lesson1 = client.get("/courses/python-basics/lessons/1")
    assert lesson1.status_code == 200
    assert b"<strong>Bold</strong>" in lesson1.data


def test_skeleton_key_does_not_restrict_unlisted_summary(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(
        tmp_path,
        payload={
            "python-basics": {
                "skeleton_keys": ["c0ffee"],
                "1": ["47a463c27f4"],
            }
        },
    )
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.get("/courses/python-basics/lessons/0")
    assert response.status_code == 200
    assert b"Overview text." in response.data


def test_non_hex_skeleton_key_is_ignored(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(
        tmp_path,
        payload={
            "python-basics": {
                "skeleton_keys": ["masterkey"],
                "1": ["47a463c27f4"],
            }
        },
    )
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    response = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "masterkey"},
    )
    assert response.status_code == 200
    assert b"Wrong access code." in response.data


def test_missing_lesson_file_returns_unavailable_content_message(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    # Simulate file disappearing after discovery.
    (content_root / "python-basics" / "lesson-1.md").unlink()

    client = app.app.test_client()
    response = client.get("/lessons/47a463c27f4.html", follow_redirects=True)

    assert response.status_code == 200
    assert b"Content is not available yet." in response.data


def test_invalid_lesson_id_returns_404_on_access_and_public_routes(
    tmp_path,
    monkeypatch,
):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()

    access_response = client.get("/courses/python-basics/lessons/999/access")
    assert access_response.status_code == 404
    assert b"Lesson not found" in access_response.data

    public_response = client.get("/courses/free-course/lessons/999")
    assert public_response.status_code == 404
    assert b"Lesson not found" in public_response.data


def test_empty_lesson_markdown_renders_unavailable_message(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    # Blank markdown produces no HTML, so template should show fallback message.
    (content_root / "free-course" / "lesson-1.md").write_text("", encoding="utf-8")

    client = app.app.test_client()
    response = client.get("/courses/free-course/lessons/1")

    assert response.status_code == 200
    assert b"Content is not available yet." in response.data


def test_course_detail_returns_404_for_unknown_slug(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    response = client.get("/courses/not-a-real-course")

    assert response.status_code == 404
    assert b"Course not found" in response.data


def test_home_shows_no_courses_when_content_root_is_missing(tmp_path, monkeypatch):
    missing_content_root = tmp_path / "does-not-exist"
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", missing_content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"Course Catalog" in response.data


def test_rate_limit_blocks_6th_access_post_attempt(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

    client = app.app.test_client()
    url = "/courses/python-basics/lessons/1/access"
    for _ in range(5):
        response = client.post(
            url,
            data={"access_code": "wrongcode"},
            environ_overrides={"REMOTE_ADDR": "10.10.10.1"},
        )
        assert response.status_code == 200

    throttled = client.post(
        url,
        data={"access_code": "wrongcode"},
        environ_overrides={"REMOTE_ADDR": "10.10.10.1"},
    )
    assert throttled.status_code == 429


def test_rate_limit_429_includes_retry_after_header(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

    client = app.app.test_client()
    url = "/courses/python-basics/lessons/1/access"
    for _ in range(6):
        throttled = client.post(
            url,
            data={"access_code": "wrongcode"},
            environ_overrides={"REMOTE_ADDR": "10.10.10.2"},
        )

    assert throttled.status_code == 429
    assert throttled.headers.get("Retry-After") is not None


def test_blueprint_endpoints_are_registered_with_namespaces():
    endpoints = {rule.endpoint for rule in app.app.url_map.iter_rules()}

    assert "core.home" in endpoints
    assert "courses.course_detail" in endpoints
    assert "lessons.lesson_access" in endpoints
    assert "lessons.lesson_page" in endpoints
    assert "lessons.legacy_lesson_page" in endpoints


def test_legacy_unprefixed_endpoints_are_not_resolvable():
    with app.app.test_request_context("/"):
        with pytest.raises(BuildError):
            url_for("home")
        with pytest.raises(BuildError):
            url_for("course_detail", slug="python-basics")
        with pytest.raises(BuildError):
            url_for("lesson_access", slug="python-basics", lesson_id=1)


def test_global_429_handler_is_registered_from_core_blueprint_module():
    handler = app.app.error_handler_spec[None][429][TooManyRequests]

    assert handler.__name__ == "handle_rate_limit_exceeded"
    assert handler.__module__ == "minilms.routes.core"


def test_unknown_route_uses_custom_404_page():
    client = app.app.test_client()

    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert b"Page not found" in response.data
    assert b"The page you requested does not exist." in response.data


def test_unhandled_exception_uses_custom_500_page_without_error_leak(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    def raise_internal_error(*_args, **_kwargs):
        raise RuntimeError("sensitive stack detail")

    monkeypatch.setitem(app.app.config, "MINILMS_LOAD_LESSON_CONTENT", raise_internal_error)

    client = app.app.test_client()
    response = client.get("/courses/free-course/lessons/1")

    assert response.status_code == 500
    assert b"Something went wrong" in response.data
    assert b"An unexpected error occurred." in response.data
    assert b"sensitive stack detail" not in response.data


def test_valid_access_code_succeeds_under_threshold_with_rate_limit_enabled(
    tmp_path,
    monkeypatch,
):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

    client = app.app.test_client()
    response = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "47a463c27f4"},
        environ_overrides={"REMOTE_ADDR": "10.10.10.3"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/courses/python-basics/lessons/1"


def test_rate_limits_are_separate_for_different_ips(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")

    client = app.app.test_client()
    url = "/courses/python-basics/lessons/1/access"
    for _ in range(6):
        first_ip = client.post(
            url,
            data={"access_code": "wrongcode"},
            environ_overrides={"REMOTE_ADDR": "10.10.10.4"},
        )

    second_ip = client.post(
        url,
        data={"access_code": "wrongcode"},
        environ_overrides={"REMOTE_ADDR": "10.10.10.5"},
    )

    assert first_ip.status_code == 429
    assert second_ip.status_code == 200


def test_security_headers_are_applied_on_html_responses(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("Content-Security-Policy") is not None
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"


def test_hsts_header_is_added_when_request_is_https(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    response = client.get("/", environ_overrides={"HTTP_X_FORWARDED_PROTO": "https"})

    assert response.status_code == 200
    assert response.headers.get("Strict-Transport-Security") is not None


def test_force_https_redirect_when_enabled(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)
    monkeypatch.setenv("FORCE_HTTPS", "true")

    client = app.app.test_client()
    response = client.get("/")

    assert response.status_code == 308
    assert response.headers["Location"].startswith("https://")


def test_session_persists_unlock_across_requests(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    
    # 1. Access code entry redirects to clean URL
    response = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "47a463c27f4"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/courses/python-basics/lessons/1"

    # 2. Accessing the clean URL works directly
    lesson_response = client.get("/courses/python-basics/lessons/1")
    assert lesson_response.status_code == 200
    assert b"<strong>Bold</strong>" in lesson_response.data

    # 3. Requesting the lesson page again (without entering a code again) still works (session is persisted)
    lesson_response2 = client.get("/courses/python-basics/lessons/1")
    assert lesson_response2.status_code == 200


def test_locked_lesson_redirects_to_access_form(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    
    # Locked lesson without session redirects to /access page
    response = client.get("/courses/python-basics/lessons/1")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/courses/python-basics/lessons/1/access")


def test_legacy_hex_url_redirects_and_grants_session(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    
    # Access legacy hex URL -> redirects with 308 to clean URL and unlocks session
    response = client.get("/lessons/47a463c27f4.html?slug=python-basics&lesson_id=1")
    assert response.status_code == 308
    assert response.headers["Location"] == "/courses/python-basics/lessons/1"

    # Following the redirect should load the content successfully (as session is unlocked)
    lesson_response = client.get("/courses/python-basics/lessons/1")
    assert lesson_response.status_code == 200
    assert b"<strong>Bold</strong>" in lesson_response.data


def test_session_does_not_leak_across_courses(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(
        tmp_path,
        payload={
            "python-basics": {"1": ["47a463c27f4"]},
            "it_sec": {"1": ["a1b2c3"]}
        }
    )
    # Add an empty lesson file for it_sec
    it_sec_dir = content_root / "it_sec"
    it_sec_dir.mkdir(parents=True, exist_ok=True)
    (it_sec_dir / "lesson-1.md").write_text("# IT Sec Lesson 1", encoding="utf-8")

    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    
    # Unlock python-basics lesson 1
    client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "47a463c27f4"},
    )
    
    # Check it_sec lesson 1 is still locked
    response = client.get("/courses/it_sec/lessons/1")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/courses/it_sec/lessons/1/access")


def test_unlocked_set_in_template(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    access_file = setup_access_codes(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(app, "ACCESS_CODES_FILE", access_file)

    client = app.app.test_client()
    
    # 1. Initially detail page says REQUIRE ACCESS KEY
    detail_pre = client.get("/courses/python-basics")
    assert b"REQUIRE ACCESS KEY" in detail_pre.data
    assert b"VIEW LESSON" not in detail_pre.data

    # 2. Unlock the lesson
    client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "47a463c27f4"},
    )
    
    # 3. Now course detail shows VIEW LESSON
    detail_post = client.get("/courses/python-basics")
    assert b"VIEW LESSON" in detail_post.data
