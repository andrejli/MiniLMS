# MiniLMS

MiniLMS is a lightweight Flask-based learning platform
that loads course content from Markdown files.

## Current features
- Course catalog generated from content folders.
- Public lessons (no key required).
- Restricted lessons protected by hex access codes.
- Access codes stored in JSON (`access.json`) instead of hardcoded values.
- Responsive PIP-Boy themed UI.

## Project structure
- `app.py`: Flask app and routing.
- `content/lessons/`: Course and lesson Markdown files.
- `templates/`: Jinja templates.
- `static/css/style.css`: UI styles.
- `access.json`: Restricted lesson access codes.
- `tests/test_app.py`: Functional tests.

## Run locally
1. Create and activate a virtual environment.
2. Install dependencies.
3. Start the Flask app.

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open http://localhost:5000/ in your browser.

## Access code configuration
Restricted lessons are configured in `access.json`.

Example:

```json
{
	"python-basics": {
		"skeleton_keys": ["c0ffee", "deadbeef"],
		"0": ["a15555"],
		"1": ["47a463c27f4", "47a463c27f4cc"]
	}
}
```

Notes:
- Key format is
	`"course-slug" -> { "skeleton_keys": [...],`
	`"lesson_id": ["hex_code_1", "hex_code_2"] }`.
- Optional `skeleton_keys` are valid for every lesson in that course.
- Every key in `access.json` must be a hex code (`[0-9a-f]`, length 6-64).
- Lessons not listed in `access.json` are treated as public.
- Access codes are case-insensitive at validation time.

## Add a new course
1. Create a folder in `content/lessons/<course-slug>/`.
2. Add `Summary.md` and `lesson-<n>.md` files.
3. Optionally add lesson IDs to `access.json` to require keys.

## Run tests
```bash
python -m pytest -q
```

## Changelog

### 2026-06-04
- Added a free course with public lessons (`content/lessons/free-course`).
- Added JSON-based access control via `access.json`.
- Replaced hardcoded restricted lesson map in app logic
	with `access.json` lookup.
- Added route behavior for public lessons (no key)
	and restricted lessons (access key flow).
- Simplified frontend assets by removing unused cart/checkout/privacy CSS
	and removing `static/js/security.js`.
- Fixed responsive CSS media-query structure and verified rendering across breakpoints.
- Expanded test coverage for free-vs-restricted lesson flows
	and JSON access-code behavior.
