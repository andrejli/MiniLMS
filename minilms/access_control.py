"""Access-code loading and validation helpers."""

from pathlib import Path
import json
import re

HEX_ACCESS_CODE_RE = re.compile(r"^[0-9a-f]{6,64}$")


def is_hex_access_code(value):
    """Return True when a value matches the accepted hex key format."""
    return bool(HEX_ACCESS_CODE_RE.fullmatch(value))


def load_access_codes(access_codes_file):
    """Load and normalize access control data from access.json."""
    if not Path(access_codes_file).exists():
        return {}
    try:
        payload = json.loads(Path(access_codes_file).read_text(encoding="utf-8"))
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
                    if not isinstance(code, str):
                        continue
                    normalized_code = code.strip().lower()
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
                if not isinstance(code, str):
                    continue
                normalized_code = code.strip().lower()
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
    return access_code in get_lesson_access_codes(access_codes_file, course_slug, lesson_id)


def find_lesson_by_access_code(access_codes_file, access_code):
    """Resolve a code to a lesson when explicit lesson context is missing."""
    for course_slug, course_access in load_access_codes(access_codes_file).items():
        lesson_codes = course_access.get("lessons", {})
        skeleton_keys = course_access.get("skeleton_keys", [])
        for lesson_id, codes in lesson_codes.items():
            if access_code in codes:
                return course_slug, lesson_id
        if access_code in skeleton_keys:
            for lesson_id in sorted(lesson_codes.keys()):
                return course_slug, lesson_id
    return None
