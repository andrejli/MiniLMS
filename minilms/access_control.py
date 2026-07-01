"""Access-code loading and validation helpers."""

from pathlib import Path
import json
import re
import hashlib
import os
import hmac
from datetime import datetime, timezone
from functools import lru_cache

HEX_ACCESS_CODE_RE = re.compile(r"^[0-9a-f]{6,64}$")


def is_hex_access_code(value):
    """Return True when a value matches the accepted hex key format."""
    return bool(HEX_ACCESS_CODE_RE.fullmatch(value))


def hash_access_code(code: str) -> str:
    """Hash an access code using PBKDF2-SHA256."""
    salt = os.urandom(16)
    iterations = 100000
    dk = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_access_code(code: str, stored_entry) -> bool:
    """Verify a user-submitted code against a stored hash or plaintext.

    ``stored_entry`` can be:
    * a ``str`` — plaintext or ``pbkdf2_sha256$...`` hash (no expiry)
    * a ``dict`` with keys ``"hash"`` and optional ``"expires_at"`` (ISO-8601 UTC)
    """
    if isinstance(stored_entry, dict):
        stored_hash = stored_entry.get("hash", "")
        expires_at = stored_entry.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                if expiry.tzinfo is None:
                    # Treat naive timestamps as UTC
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expiry:
                    return False
            except (ValueError, TypeError):
                return False
    else:
        stored_hash = stored_entry

    if not stored_hash.startswith("pbkdf2_sha256$"):
        return code == stored_hash

    try:
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False
        _, iterations_str, salt_hex, hash_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        dk = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected_hash)
    except Exception:
        return False


@lru_cache(maxsize=16)
def _load_access_codes_cached(access_codes_file_str, mtime):
    """Normalized loader wrapper that caches output based on mtime."""
    access_codes_file = Path(access_codes_file_str)
    if not access_codes_file.exists():
        return {}
    try:
        payload = json.loads(access_codes_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}

    normalized = {}
    for course_slug, course_codes in payload.items():
        if not isinstance(course_codes, dict):
            continue
        lesson_codes = {}
        skeleton_keys = []
        for lesson_id, codes in course_codes.items():
            if lesson_id == "skeleton_keys":
                if not isinstance(codes, list):
                    continue
                for code in codes:
                    if isinstance(code, dict):
                        h = code.get("hash", "").strip()
                        if h.startswith("pbkdf2_sha256$") or is_hex_access_code(h):
                            skeleton_keys.append(code)
                        continue
                    if not isinstance(code, str):
                        continue
                    val = code.strip()
                    if val.startswith("pbkdf2_sha256$"):
                        skeleton_keys.append(val)
                    else:
                        normalized_code = val.lower()
                        if normalized_code and is_hex_access_code(normalized_code):
                            skeleton_keys.append(normalized_code)
                continue

            if not isinstance(codes, list):
                continue
            try:
                lesson_id_int = int(lesson_id)
            except (TypeError, ValueError):
                continue

            normalized_codes = []
            for code in codes:
                if isinstance(code, dict):
                    h = code.get("hash", "").strip()
                    if h.startswith("pbkdf2_sha256$") or is_hex_access_code(h):
                        normalized_codes.append(code)
                    continue
                if not isinstance(code, str):
                    continue
                val = code.strip()
                if val.startswith("pbkdf2_sha256$"):
                    normalized_codes.append(val)
                else:
                    normalized_code = val.lower()
                    if normalized_code and is_hex_access_code(normalized_code):
                        normalized_codes.append(normalized_code)
            if normalized_codes:
                lesson_codes[lesson_id_int] = normalized_codes

        if lesson_codes or skeleton_keys:
            normalized[str(course_slug)] = {
                "skeleton_keys": skeleton_keys,
                "lessons": lesson_codes,
            }
    return normalized


def load_access_codes(access_codes_file):
    """Load and normalize access control data from access.json."""
    path = Path(access_codes_file)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return _load_access_codes_cached(str(path), mtime)


def get_course_skeleton_keys(access_codes_file, course_slug):
    """Return the list of skeleton keys for a course slug."""
    return load_access_codes(access_codes_file).get(course_slug, {}).get("skeleton_keys", [])


def get_lesson_access_codes(access_codes_file, course_slug, lesson_id):
    """Return all valid codes for one lesson."""
    course_access = load_access_codes(access_codes_file).get(course_slug, {})
    lesson_codes = course_access.get("lessons", {}).get(lesson_id, [])
    if not lesson_codes:
        return []
    skeleton_keys = course_access.get("skeleton_keys", [])
    return lesson_codes + [code for code in skeleton_keys if code not in lesson_codes]


def is_access_code_valid_for_lesson(access_codes_file, course_slug, lesson_id, access_code):
    """Check whether a provided code can unlock a specific lesson."""
    valid_codes = get_lesson_access_codes(access_codes_file, course_slug, lesson_id)
    for stored_code in valid_codes:
        if verify_access_code(access_code, stored_code):
            return True
    return False


def find_lesson_by_access_code(access_codes_file, access_code):
    """Resolve a code to a lesson when explicit lesson context is missing."""
    for course_slug, course_access in load_access_codes(access_codes_file).items():
        lesson_codes = course_access.get("lessons", {})
        skeleton_keys = course_access.get("skeleton_keys", [])
        for lesson_id, codes in lesson_codes.items():
            for stored_code in codes:
                if verify_access_code(access_code, stored_code):
                    return course_slug, lesson_id
        for stored_code in skeleton_keys:
            if verify_access_code(access_code, stored_code):
                for lesson_id in sorted(lesson_codes.keys()):
                    return course_slug, lesson_id
    return None
