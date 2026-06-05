from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app


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
    assert response.headers["Location"].startswith("/lessons/47a463c27f4.html")
    assert "slug=python-basics" in response.headers["Location"]
    assert "lesson_id=1" in response.headers["Location"]

    lesson_response = client.get("/lessons/47a463c27f4.html")
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
    assert unlocked.headers["Location"].startswith("/lessons/a15555.html")
    assert "lesson_id=0" in unlocked.headers["Location"]


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
    assert response.headers["Location"].startswith("/lessons/abc123.html")
    assert "lesson_id=1" in response.headers["Location"]


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
    assert lesson0.headers["Location"].startswith("/lessons/c0ffee.html")
    assert "lesson_id=0" in lesson0.headers["Location"]

    lesson1 = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "c0ffee"},
    )
    assert lesson1.status_code == 302
    assert lesson1.headers["Location"].startswith("/lessons/c0ffee.html")
    assert "lesson_id=1" in lesson1.headers["Location"]


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
    response = client.get("/lessons/47a463c27f4.html")

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
