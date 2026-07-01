#!/usr/bin/env python3
"""CLI to generate, list, and revoke time-limited hex access codes.

Usage:
  python manage_access.py generate <course> <lesson> [--days N | --hours N | --expires YYYY-MM-DD]
  python manage_access.py gen-skeleton <course> [--days N | --hours N | --expires YYYY-MM-DD]
  python manage_access.py list [course]
  python manage_access.py revoke <code-id>
  python manage_access.py rehash [--dry-run]
"""

import argparse
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from minilms.access_control import hash_access_code, is_hex_access_code

ACCESS_FILE = Path(__file__).parent / "access.json"


def _resolve_file(path_str):
    return Path(path_str) if path_str else ACCESS_FILE


def _load():
    try:
        return json.loads(ACCESS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("Error: access.json not found or invalid.", file=sys.stderr)
        sys.exit(1)


def _save(data):
    ACCESS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def cmd_generate(args):
    global ACCESS_FILE
    ACCESS_FILE = _resolve_file(getattr(args, "file", None))
    data = _load()
    course = args.course
    lesson_str = str(args.lesson)

    if course not in data:
        print(f"Error: course '{course}' not found in access.json.", file=sys.stderr)
        sys.exit(1)

    if lesson_str not in data[course]:
        data[course][lesson_str] = []

    now = datetime.now(timezone.utc)
    if args.expires:
        try:
            expires = datetime.fromisoformat(args.expires)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        except ValueError:
            print("Error: invalid --expires format. Use YYYY-MM-DD or ISO-8601.", file=sys.stderr)
            sys.exit(1)
    elif args.days:
        expires = now + timedelta(days=args.days)
    elif args.hours:
        expires = now + timedelta(hours=args.hours)
    else:
        expires = now + timedelta(days=7)

    plaintext = secrets.token_hex(16)
    hashed = hash_access_code(plaintext)
    code_id = "K-" + secrets.token_hex(4)

    entry = {
        "id": code_id,
        "hash": hashed,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }

    data[course][lesson_str].append(entry)
    _save(data)

    print(f"ID:         {code_id}")
    print(f"Course:     {course}")
    print(f"Lesson:     {args.lesson}")
    print(f"Expires:    {expires.isoformat()}")
    print(f"Code:       {plaintext}")
    print()
    print(f"Store the code above to the user (e.g. via email).")
    print(f"It will expire on {expires.strftime('%Y-%m-%d %H:%M UTC')}.")
    print(f"Use `revoke {code_id}` to invalidate it early.")


def _list_codes(data, course_filter):
    found = False
    for course in sorted(data):
        if course_filter and course != course_filter:
            continue
        for key, codes in data[course].items():
            if key == "skeleton_keys":
                for code in codes:
                    if isinstance(code, dict) and "expires_at" in code:
                        found = True
                        cid = code.get("id", "??")
                        expires = code["expires_at"]
                        print(f"{cid}  {course}  skeleton        expires {expires}")
                    elif isinstance(code, dict):
                        found = True
                        cid = code.get("id", "??")
                        print(f"{cid}  {course}  skeleton        (no expiry)")
                    elif isinstance(code, str) and code.startswith("pbkdf2_sha256$"):
                        found = True
                        parts = code.split("$")
                        suffix = parts[-1][:8] if len(parts) == 4 else code[:16]
                        print(f"         {course}  skeleton        (permanent hash ...{suffix})")
                    elif isinstance(code, str) and is_hex_access_code(code):
                        found = True
                        print(f"         {course}  skeleton        (permanent plaintext {code[:12]}...)")
                continue
            for code in codes:
                if isinstance(code, dict) and "expires_at" in code:
                    found = True
                    cid = code.get("id", "??")
                    expires = code["expires_at"]
                    print(f"{cid}  {course}  lesson {key}  expires {expires}")
                elif isinstance(code, dict):
                    found = True
                    cid = code.get("id", "??")
                    print(f"{cid}  {course}  lesson {key}  (no expiry)")
                elif isinstance(code, str) and code.startswith("pbkdf2_sha256$"):
                    found = True
                    parts = code.split("$")
                    suffix = parts[-1][:8] if len(parts) == 4 else code[:16]
                    print(f"         {course}  lesson {key}  (permanent hash ...{suffix})")
                elif isinstance(code, str) and is_hex_access_code(code):
                    found = True
                    print(f"         {course}  lesson {key}  (permanent plaintext {code[:12]}...)")
    return found


def cmd_list(args):
    global ACCESS_FILE
    ACCESS_FILE = _resolve_file(getattr(args, "file", None))
    data = _load()
    if not _list_codes(data, args.course):
        print("No codes found.")


def _remove_by_id(data, needle):
    removed = 0
    for course in data:
        for key in list(data[course].keys()):
            if key == "skeleton_keys":
                remaining = []
                for code in data[course][key]:
                    match = False
                    if isinstance(code, dict):
                        cid = code.get("id", "")
                        if cid.lower() == needle:
                            match = True
                    if not match:
                        remaining.append(code)
                    else:
                        removed += 1
                        print(f"Removed  {cid}  ({course} skeleton)")
                data[course][key] = remaining
                continue
            remaining = []
            for code in data[course][key]:
                match = False
                if isinstance(code, dict):
                    cid = code.get("id", "")
                    if cid.lower() == needle:
                        match = True
                if not match:
                    remaining.append(code)
                else:
                    removed += 1
                    print(f"Removed  {cid}  ({course} lesson {key})")
            data[course][key] = remaining
    return removed


def cmd_revoke(args):
    global ACCESS_FILE
    ACCESS_FILE = _resolve_file(getattr(args, "file", None))
    data = _load()
    needle = args.code_id.lower()
    removed = _remove_by_id(data, needle)
    if removed:
        _save(data)
        print(f"Revoked {removed} code(s).")
    else:
        print(f"No code with ID '{needle}' found. Use `list` to see all IDs.")


def cmd_gen_skeleton(args):
    global ACCESS_FILE
    ACCESS_FILE = _resolve_file(getattr(args, "file", None))
    data = _load()
    course = args.course

    if course not in data:
        print(f"Error: course '{course}' not found in access.json.", file=sys.stderr)
        sys.exit(1)

    if "skeleton_keys" not in data[course]:
        data[course]["skeleton_keys"] = []

    now = datetime.now(timezone.utc)
    if args.expires:
        try:
            expires = datetime.fromisoformat(args.expires)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        except ValueError:
            print("Error: invalid --expires format. Use YYYY-MM-DD or ISO-8601.", file=sys.stderr)
            sys.exit(1)
    elif args.days:
        expires = now + timedelta(days=args.days)
    elif args.hours:
        expires = now + timedelta(hours=args.hours)
    else:
        expires = None

    plaintext = secrets.token_hex(16)
    hashed = hash_access_code(plaintext)
    code_id = "K-" + secrets.token_hex(4)

    if expires:
        entry = {
            "id": code_id,
            "hash": hashed,
            "created_at": now.isoformat(),
            "expires_at": expires.isoformat(),
        }
        expiry_label = expires.isoformat()
    else:
        entry = {
            "id": code_id,
            "hash": hashed,
            "created_at": now.isoformat(),
        }
        expiry_label = "never"

    data[course]["skeleton_keys"].append(entry)
    _save(data)

    print(f"ID:         {code_id}")
    print(f"Course:     {course}")
    print(f"Type:       skeleton key (unlocks all lessons)")
    print(f"Expires:    {expiry_label}")
    print(f"Code:       {plaintext}")
    print()
    print(f"Store the code above to the user (e.g. via email).")
    if expires:
        print(f"It will expire on {expires.strftime('%Y-%m-%d %H:%M UTC')}.")
    print(f"Use `revoke {code_id}` to invalidate it early.")


def cmd_rehash(args):
    global ACCESS_FILE
    ACCESS_FILE = _resolve_file(getattr(args, "file", None))
    data = _load()
    now = datetime.now(timezone.utc)
    converted = 0

    for course in data:
        for key in list(data[course].keys()):
            items = data[course][key]
            if not isinstance(items, list):
                continue
            new_items = []
            for code in items:
                if isinstance(code, dict):
                    new_items.append(code)
                elif isinstance(code, str):
                    if code.startswith("pbkdf2_sha256$"):
                        # Already hashed but has no ID — wrap it
                        new_code = {
                            "id": "K-" + secrets.token_hex(4),
                            "hash": code,
                            "created_at": now.isoformat(),
                        }
                        new_items.append(new_code)
                        converted += 1
                        print(f"  Wrapped hash for {course}/{key}")
                    elif is_hex_access_code(code):
                        new_code = {
                            "id": "K-" + secrets.token_hex(4),
                            "hash": hash_access_code(code),
                            "created_at": now.isoformat(),
                        }
                        new_items.append(new_code)
                        converted += 1
                        print(f"  Hashed plaintext {code[:12]}... for {course}/{key}")
                    else:
                        # Unknown string format — keep as-is
                        new_items.append(code)
                else:
                    new_items.append(code)
            data[course][key] = new_items

    if converted:
        if getattr(args, "dry_run", False):
            print(f"\nWould convert {converted} code(s). Pass --file and omit --dry-run to apply.")
        else:
            _save(data)
            print(f"\nConverted {converted} code(s). access.json updated.")
    else:
        print("No legacy codes found — everything is already hashed.")


def main():
    parser = argparse.ArgumentParser(
        description="Manage time-limited hex access codes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Generate a code valid for 7 days (default)\n"
            "  python manage_access.py generate python-basics 1\n"
            "\n"
            "  # Generate a code valid for 3 days\n"
            "  python manage_access.py generate python-basics 1 --days 3\n"
            "\n"
            "  # Generate a code valid for 12 hours\n"
            "  python manage_access.py generate it_sec 2 --hours 12\n"
            "\n"
            "  # Generate a code that expires on a specific date\n"
            "  python manage_access.py generate python-basics 0 --expires 2026-09-01\n"
            "\n"
            "  # List all codes\n"
            "  python manage_access.py list\n"
            "  python manage_access.py list python-basics\n"
            "\n"
            "  # Generate a skeleton key for a course (never expires)\n"
            "  python manage_access.py gen-skeleton python-basics\n"
            "\n"
            "  # Generate a skeleton key valid for 30 days\n"
            "  python manage_access.py gen-skeleton python-basics --days 30\n"
            "\n"
            "  # Revoke a code (use the ID shown by `list`)\n"
            "  python manage_access.py revoke K-a1b2c3d4\n"
            "\n"
            "  # Use a different access file (default: ./access.json)\n"
            "  python manage_access.py --file /path/to/access.json list\n"
            "\n"
            "  # Convert legacy plaintext codes to hashed + ID entries\n"
            "  python manage_access.py rehash\n"
            "  python manage_access.py rehash --dry-run\n"
        ),
    )
    parser.add_argument(
        "--file",
        help="Path to access.json (default: ./access.json)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser(
        "generate",
        help="Generate a new time-limited code",
        epilog=(
            "Examples:\n"
            "  python manage_access.py generate python-basics 1 --days 7\n"
            "  python manage_access.py generate it_sec 2 --hours 12\n"
            "  python manage_access.py generate python-basics 0 --expires 2026-09-01\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gen.add_argument("course", help="Course slug (e.g. python-basics)")
    gen.add_argument("lesson", type=int, help="Lesson ID (e.g. 1)")
    expiry = gen.add_mutually_exclusive_group()
    expiry.add_argument("--days", type=int, help="Days until expiry (default: 7)")
    expiry.add_argument("--hours", type=int, help="Hours until expiry")
    expiry.add_argument("--expires", help="Expiry date (ISO-8601 or YYYY-MM-DD)")
    gen.set_defaults(func=cmd_generate)

    lst = sub.add_parser(
        "list",
        help="List all time-limited codes",
        epilog=(
            "Examples:\n"
            "  python manage_access.py list\n"
            "  python manage_access.py list python-basics\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lst.add_argument("course", nargs="?", default=None, help="Optional course slug to filter")
    lst.set_defaults(func=cmd_list)

    rev = sub.add_parser(
        "revoke",
        help="Revoke a code by its ID (shown by `list`)",
        epilog=(
            "Examples:\n"
            "  python manage_access.py revoke K-a1b2c3d4\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rev.add_argument("code_id", help="Code ID (e.g. K-a1b2c3d4 — shown by `list`)")
    rev.set_defaults(func=cmd_revoke)

    sk = sub.add_parser(
        "gen-skeleton",
        help="Generate a skeleton (master) key for a course",
        epilog=(
            "Examples:\n"
            "  python manage_access.py gen-skeleton python-basics\n"
            "  python manage_access.py gen-skeleton python-basics --days 30\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sk.add_argument("course", help="Course slug (e.g. python-basics)")
    sk_expiry = sk.add_mutually_exclusive_group()
    sk_expiry.add_argument("--days", type=int, help="Days until expiry")
    sk_expiry.add_argument("--hours", type=int, help="Hours until expiry")
    sk_expiry.add_argument("--expires", help="Expiry date (ISO-8601 or YYYY-MM-DD)")
    sk.set_defaults(func=cmd_gen_skeleton)

    rh = sub.add_parser(
        "rehash",
        help="Convert legacy plaintext codes to hashed entries with IDs",
        epilog=(
            "Examples:\n"
            "  python manage_access.py rehash --dry-run\n"
            "  python manage_access.py rehash\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rh.add_argument("--dry-run", action="store_true", help="Show what would be converted without saving")
    rh.set_defaults(func=cmd_rehash)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
