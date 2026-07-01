from pathlib import Path
import json
import sys
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from minilms.access_control import verify_access_code, hash_access_code, is_hex_access_code


# ── verify_access_code with dict entries ──────────────────────────────


def test_dict_entry_valid_not_expired():
    plain = "a1b2c3d4e5f6"
    hashed = hash_access_code(plain)
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    entry = {"hash": hashed, "expires_at": future}
    assert verify_access_code(plain, entry) is True


def test_dict_entry_expired():
    plain = "deadbeef1234"
    hashed = hash_access_code(plain)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    entry = {"hash": hashed, "expires_at": past}
    assert verify_access_code(plain, entry) is False


def test_dict_entry_no_expiry():
    plain = "c0ffee"
    hashed = hash_access_code(plain)
    entry = {"hash": hashed}
    assert verify_access_code(plain, entry) is True


def test_dict_entry_wrong_code():
    plain = "aabbcc"
    hashed = hash_access_code(plain)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    entry = {"hash": hashed, "expires_at": future}
    assert verify_access_code("wrong", entry) is False


def test_dict_entry_bad_expiry_format():
    plain = "deadbeef"
    hashed = hash_access_code(plain)
    entry = {"hash": hashed, "expires_at": "not-a-date"}
    assert verify_access_code(plain, entry) is False


def test_string_entry_still_works():
    plain = "47a463c27f4"
    assert verify_access_code(plain, plain) is True
    assert verify_access_code("wrong", plain) is False


def test_hashed_string_entry_still_works():
    plain = "secretkey"
    hashed = hash_access_code(plain)
    assert verify_access_code(plain, hashed) is True
    assert verify_access_code("wrong", hashed) is False


# ── manage_access.py CLI ─────────────────────────────────────────────


MANAGE = [sys.executable, str(PROJECT_ROOT / "manage_access.py")]


@pytest.fixture
def access_file(tmp_path):
    src = PROJECT_ROOT / "access.json"
    dst = tmp_path / "access.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def _read_access(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_generate_code_creates_entry(access_file):
    data_before = _read_access(access_file)
    course = "python-basics"
    lesson = "1"
    existing_count = len(data_before.get(course, {}).get(lesson, []))

    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "generate", course, "1", "--days", "30"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "Code:" in result.stdout
    assert "ID:" in result.stdout

    data_after = _read_access(access_file)
    codes = data_after[course][lesson]
    assert len(codes) == existing_count + 1

    new_entry = codes[-1]
    assert isinstance(new_entry, dict)
    assert new_entry["id"].startswith("K-")
    assert "hash" in new_entry
    assert "expires_at" in new_entry
    assert "created_at" in new_entry
    assert new_entry["hash"].startswith("pbkdf2_sha256$")


def test_generate_shows_code_on_stdout(access_file):
    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "generate", "python-basics", "1", "--hours", "1"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "ID:" in result.stdout
    assert "Code:" in result.stdout
    # Extract the ID
    for line in result.stdout.splitlines():
        if line.startswith("ID:"):
            cid = line.split(":", 1)[1].strip()
            assert cid.startswith("K-")
            break
    else:
        pytest.fail("ID line not found in output")
    # Extract the code
    for line in result.stdout.splitlines():
        if line.startswith("Code:"):
            code = line.split(":", 1)[1].strip()
            assert is_hex_access_code(code)
            break
    else:
        pytest.fail("Code line not found in output")


def test_list_shows_generated_code(access_file):
    # Insert a known time-limited entry
    data = _read_access(access_file)
    hashed = hash_access_code("testcode123")
    entry = {
        "id": "K-listtest",
        "hash": hashed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    data.setdefault("python-basics", {}).setdefault("1", []).append(entry)
    access_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "list"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "expires" in result.stdout
    assert "K-listtest" in result.stdout


def test_revoke_code_by_id(access_file):
    data = _read_access(access_file)
    hashed = hash_access_code("revokeme123")
    code_id = "K-testrevoke"
    entry = {
        "id": code_id,
        "hash": hashed,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    data.setdefault("python-basics", {}).setdefault("1", []).append(entry)
    access_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "revoke", code_id],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "Revoked" in result.stdout
    assert "K-testrevoke" in result.stdout

    data_after = _read_access(access_file)
    assert entry not in data_after["python-basics"]["1"]


# ── Skeleton keys ────────────────────────────────────────────────────


def test_gen_skeleton_creates_entry(access_file):
    data_before = _read_access(access_file)
    existing = len(data_before.get("python-basics", {}).get("skeleton_keys", []))

    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "gen-skeleton", "python-basics"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "ID:" in result.stdout
    assert "Code:" in result.stdout
    assert "skeleton" in result.stdout

    data_after = _read_access(access_file)
    keys = data_after["python-basics"]["skeleton_keys"]
    assert len(keys) == existing + 1

    new_entry = keys[-1]
    assert new_entry["id"].startswith("K-")
    assert "hash" in new_entry
    assert "created_at" in new_entry
    assert new_entry["hash"].startswith("pbkdf2_sha256$")
    # No expiry → no expires_at
    assert "expires_at" not in new_entry


def test_gen_skeleton_with_expiry(access_file):
    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "gen-skeleton", "python-basics", "--days", "7"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "Expires:" in result.stdout

    data = _read_access(access_file)
    keys = data["python-basics"]["skeleton_keys"]
    newest = keys[-1]
    assert "expires_at" in newest

    # Clean up
    data["python-basics"]["skeleton_keys"] = keys[:-1]
    access_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_skeleton_key_revokable_by_id(access_file):
    data = _read_access(access_file)
    code_id = "K-sktest"
    hashed = hash_access_code("skeletonplain")
    entry = {"id": code_id, "hash": hashed, "created_at": "now"}
    data.setdefault("python-basics", {}).setdefault("skeleton_keys", []).append(entry)
    access_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        MANAGE + ["--file", str(access_file), "revoke", code_id],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "Revoked" in result.stdout

    data_after = _read_access(access_file)
    assert entry not in data_after["python-basics"]["skeleton_keys"]


# ── Integration: generated code unlocks lesson in the app ────────────


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")


def test_generated_code_unlocks_lesson_via_app(tmp_path, monkeypatch):
    from app import app

    content_root = tmp_path / "lessons"
    course_dir = content_root / "python-basics"
    course_dir.mkdir(parents=True)
    (course_dir / "lesson-1.md").write_text("# Lesson 1\n\nContent.", encoding="utf-8")

    monkeypatch.setattr("app.CONTENT_ROOT", content_root)

    plain = "integrationtest123"
    hashed = hash_access_code(plain)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    entry = {"hash": hashed, "expires_at": future}

    access_data = {"python-basics": {"1": [entry]}}
    access_file = tmp_path / "access.json"
    access_file.write_text(json.dumps(access_data), encoding="utf-8")
    monkeypatch.setattr("app.ACCESS_CODES_FILE", access_file)

    client = app.test_client()

    # POST the code
    resp = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": plain},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/courses/python-basics/lessons/1"

    lesson = client.get("/courses/python-basics/lessons/1")
    assert lesson.status_code == 200
    assert b"Content." in lesson.data


def test_expired_code_rejected_by_app(tmp_path, monkeypatch):
    from app import app

    content_root = tmp_path / "lessons"
    course_dir = content_root / "python-basics"
    course_dir.mkdir(parents=True)
    (course_dir / "lesson-1.md").write_text("# Lesson 1\n\nContent.", encoding="utf-8")

    monkeypatch.setattr("app.CONTENT_ROOT", content_root)

    plain = "expiredcode999"
    hashed = hash_access_code(plain)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    entry = {"hash": hashed, "expires_at": past}

    access_data = {"python-basics": {"1": [entry]}}
    access_file = tmp_path / "access.json"
    access_file.write_text(json.dumps(access_data), encoding="utf-8")
    monkeypatch.setattr("app.ACCESS_CODES_FILE", access_file)

    client = app.test_client()
    resp = client.post(
        "/courses/python-basics/lessons/1/access",
        data={"access_code": plain},
    )
    assert resp.status_code == 200
    assert b"Wrong access code." in resp.data
