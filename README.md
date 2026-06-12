# MiniLMS

MiniLMS is a lightweight Flask-based learning platform
that loads course content from Markdown files.

## Current features
- Course catalog generated from content folders.
- Public lessons (no key required).
- Restricted lessons protected by hex access codes.
- Access codes stored in JSON (`access.json`) instead of hardcoded values.
- Security headers (CSP, HSTS on HTTPS, frame/mime/referrer/XSS protections).
- Responsive PIP-Boy themed UI.

## Project structure
- `app.py`: Flask app and routing.
- `content/lessons/`: Course and lesson Markdown files.
- `templates/`: Jinja templates.
- `static/css/style.css`: UI styles.
- `minilms/`: Modular backend components (routes, access control, content service, security headers).
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

## Rate limiting
MiniLMS includes environment-driven request throttling via Flask-Limiter.

Default policies:
- Global: `120/hour` per IP.
- Global burst: `30/minute` per IP.
- Access submission (`POST /courses/<slug>/lessons/<id>/access`):
	`5/minute` and `20/hour` per IP plus route path.

Environment keys:
- `RATE_LIMIT_ENABLED` (`true|false`, default `true`)
- `RATE_LIMIT_STORAGE_URI` (default `memory://`; use Redis in production)
- `RATE_LIMIT_GLOBAL_HOURLY` (default `120/hour`)
- `RATE_LIMIT_GLOBAL_MINUTE` (default `30/minute`)
- `RATE_LIMIT_ACCESS_POST_MINUTE` (default `5/minute`)
- `RATE_LIMIT_ACCESS_POST_HOURLY` (default `20/hour`)

Throttled requests return HTTP `429` with retry guidance and a `Retry-After` header.

## Changelog

### 2026-06-10
- Implemented Flask-Limiter-based rate limiting with environment-driven configuration.
- Added global limits (`120/hour`, `30/minute`) for all routes.
- Added strict access submission limits on `POST /courses/<slug>/lessons/<id>/access` (`5/minute`, `20/hour`, keyed by IP+route).
- Added centralized HTTP 429 response handling with retry guidance and `Retry-After` support.
- Added proxy-aware IP handling via `ProxyFix` for reverse-proxy deployments.
- Added integration tests for throttle behavior (6th rapid POST blocked, header presence, valid under-threshold success, per-IP separation).
- Refactored monolithic `app.py` into modular components under `minilms/` for maintainability.
- Implemented low-dependency security-header middleware (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, X-XSS-Protection, and HSTS on HTTPS responses).
- Added tests for security-header presence, HTTPS HSTS emission, and optional force-HTTPS redirect behavior.

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
