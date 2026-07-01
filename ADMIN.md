# Admin Guide — Access Code Management

## Overview

Lessons can be protected with hex access codes. Codes are stored **hashed** in
`access.json` (never in plaintext). The admin generates a code, shares the
plaintext with the user (e.g. via email), and the system verifies the hash at
runtime.

## CLI tool: `manage_access.py`

### Generate a time-limited code

```bash
# Expires in 7 days (default)
python manage_access.py generate python-basics 1

# Expires in 3 days
python manage_access.py generate python-basics 1 --days 3

# Expires in 12 hours
python manage_access.py generate it_sec 2 --hours 12

# Expires on a specific date
python manage_access.py generate python-basics 1 --expires 2026-08-15

# Protect the summary (lesson 0) with a time-limited code
python manage_access.py generate python-basics 0 --days 1
```

Output:
```
Course:     python-basics
Lesson:     1
Expires:    2026-07-15T23:59:59+00:00
Code:       a1b2c3d4e5f6...
```

The **Code** line is the plaintext — copy and send it to the user. The hash is
stored automatically in `access.json`.

### List all codes

```bash
# All courses
python manage_access.py list

# Filter by course
python manage_access.py list python-basics
```

Example output:
```
python-basics  lesson   1  pbkdf2_sha256$a1b2c3d4...  expires 2026-07-15T23:59:59+00:00
python-basics  lesson   1  pbkdf2...e5f6g7h8           (permanent)
it_sec         lesson   2  pbkdf2_sha256$i9j0k1l2...  expires 2026-07-10T12:00:00+00:00
```

Use the hash prefix from the output to revoke a code.

### Revoke a code before it expires

```bash
# Use the hash prefix shown by `list`
python manage_access.py revoke a1b2c3d4

# Can also match the full hash suffix
python manage_access.py revoke e5f6g7h8
```

### Get help

```bash
python manage_access.py --help
python manage_access.py generate --help
python manage_access.py list --help
python manage_access.py revoke --help
```

## How expiry works

- Each code has an `expires_at` timestamp (ISO-8601, UTC).
- The server checks expiry on every access attempt.
- Expired codes are rejected with "Wrong access code."
- Expired codes remain in `access.json` until revoked — they're harmless but can
  be cleaned up with `revoke`.

## `access.json` format

Permanent codes are stored as plain strings (backward compatible):

```json
"1": ["pbkdf2_sha256$..."]
```

Time-limited codes are stored as objects:

```json
"1": [
  "pbkdf2_sha256$...",
  {
    "hash": "pbkdf2_sha256$...",
    "created_at": "2026-07-01T12:00:00+00:00",
    "expires_at": "2026-07-08T12:00:00+00:00"
  }
]
```

You can edit `access.json` by hand if needed, but using the CLI tool is
recommended to avoid hash mistakes.
