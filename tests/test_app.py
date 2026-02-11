from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import app


def setup_content(tmp_path):
    content_root = tmp_path / "lessons"
    course_dir = content_root / "python-basics"
    course_dir.mkdir(parents=True)
    (course_dir / "Summary.md").write_text("# Summary\n\nOverview text.", encoding="utf-8")
    (course_dir / "lesson-1.md").write_text("# Lesson 1\n\n**Bold** text.", encoding="utf-8")
    return content_root


def test_course_discovery_from_content(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)

    courses = app.get_courses()

    assert len(courses) == 1
    assert courses[0]["slug"] == "python-basics"
    assert courses[0]["title"] == "Python Basics"
    assert courses[0]["lessons"] == 2
    assert set(courses[0]["lesson_ids"]) == {0, 1}


def test_access_flow_and_rendered_lesson(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(
        app,
        "LESSON_HEX_ROUTES",
        {("python-basics", 1): "47a463c27f4"},
    )

    client = app.app.test_client()

    response = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": "47a463c27f4"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/lessons/47a463c27f4.html")

    lesson_response = client.get("/lessons/47a463c27f4.html")
    assert lesson_response.status_code == 200
    assert b"<strong>Bold</strong>" in lesson_response.data


def test_wrong_code_returns_404(tmp_path, monkeypatch):
    content_root = setup_content(tmp_path)
    monkeypatch.setattr(app, "CONTENT_ROOT", content_root)
    monkeypatch.setattr(
        app,
        "LESSON_HEX_ROUTES",
        {("python-basics", 1): "47a463c27f4"},
    )

    client = app.app.test_client()

    response = client.get("/lessons/badcode.html")
    assert response.status_code == 404
    assert b"Wrong code" in response.data
