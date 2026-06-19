# Session-Based Access Implementation Specification

**Target:** Replace hex-code-in-URL authorization with `Flask-Session` server-side / signed-cookie sessions.

**Status:** Draft  
**Priority:** P0 (Security — per `CRITICAL.md` §3.1)  
**Depends on:** `Flask-Session` ≥0.8.0 (new dependency)  

---

## 1. Motivation

### Current Problem

After a successful code submission at `POST /courses/<slug>/lessons/<id>/access`, the app redirects to:

```
/lessons/47a463c27f4.html?slug=python-basics&lesson_id=1
```

The hex code **is the access credential**, and it is leaked in:
- Browser history / bookmarks
- Server access logs
- HTTP `Referer` headers to external resources
- Shoulder-surfing

There is no persistent "unlocked" state — the credential must be carried on every request.

### Goal

Replace this with a **server-validated session** so that:
- After a correct code entry, `session["unlocked"]` records the grant.
- Subsequent requests to `/courses/<slug>/lessons/<id>` check the session, not the URL.
- The hex code never appears in the URL after the initial POST.

---

## 2. Design Goals

| Goal | Priority |
|------|----------|
| Hex codes removed from URLs after unlock | **Must** |
| Backward-compatible — old hex-code URLs still work (graceful redirect) | **Must** |
| Skeleton keys unlock all lessons in a course | **Must** |
| Rate limiting on access POST preserved | **Must** |
| Session does not bloat (unlocked set bounded by course/lesson count) | **Should** |
| Zero JS — all session writes happen server-side via POST | **Must** |
| No user authentication required — session is anonymous | **Must** |

### Non-Goals (Phase 2+ per `SECURITY.md`)
- User identity / login / email magic links
- Per-user token generation and revocation
- Audit logging of access events
- Hashing access codes with Argon2

---

## 3. Session Backend Selection

### Recommendation: `Flask-Session` with filesystem backend

| Backend | Pros | Cons | Verdict |
|---------|------|------|---------|
| **Null (signed cookies)** | Zero infrastructure, simple | 4 KB size limit; unlocked set visible to client (tamper-proof but readable) | Acceptable for ≤50 lessons |
| **Filesystem** | Server-side, no size limit, clean | Requires writeable `/tmp` or `instance/` dir | **Recommended default** |
| **Redis** | Fast, multi-worker safe | Extra dependency, ops overhead | Production upgrade |

Default to **filesystem** (`SESSION_TYPE="filesystem"`, `SESSION_FILE_DIR=<instance>/flask_session/`).  
Document Redis as the production upgrade (`SESSION_TYPE="redis"`).

### How the session is used

```
Cookie to client:  session=eyJ1bmxvY2tlZCI6...  (signed, not encrypted by default)
Filesystem:        flask_session/session_<random>
```

Even with signed cookies (null backend), the **unlocked set is integrity-protected** (tampering invalidates the signature), which is sufficient for this access level.

---

## 4. Session Data Schema

```python
# Stored at session["unlocked"]
{
    "python-basics": {1, 2},       # lesson IDs unlocked in this course
    "it_sec":        {1, 2, 3},    # skeleton key unlocked ALL
}
```

**Initialization guard** (every route that reads it):

```python
from flask import session

def _is_unlocked(course_slug: str, lesson_id: int) -> bool:
    unlocked: dict[str, set[int]] = session.get("unlocked", {})
    return lesson_id in unlocked.get(course_slug, set())
```

### Skeleton key semantics

When a skeleton key is validated:
```python
lesson_ids = [item["id"] for item in list_lesson_files(content_root, course_slug)]
session.setdefault("unlocked", {})
# Replace the set — skeleton unlocks ALL lessons in the course
session["unlocked"][course_slug] = set(lesson_ids)
# Equivalent to inserting every lesson_id individually
```

This means a skeleton key grants access to **future lessons too** if new `.md` files are added later (desirable for ongoing courses). If this is not desired, use `|.update()` with only the lesson_ids known at unlock time.

### Session config (app.py)

```python
app.config["SESSION_TYPE"] = os.getenv("SESSION_TYPE", "filesystem")
app.config["SESSION_FILE_DIR"] = os.getenv(
    "SESSION_FILE_DIR",
    str(Path(app.instance_path) / "flask_session"),
)
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)  # configurable
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# SESSION_COOKIE_SECURE = True  # enable in production behind HTTPS
```

---

## 5. Route Changes

### 5.1 `POST /courses/<slug>/lessons/<int:lesson_id>/access` — `lesson_access()`

**Current:** Redirects to `/lessons/<hex_id>.html?slug=...&lesson_id=...`  
**New:** On valid code, write `session["unlocked"]` and redirect to the **clean** lesson page.

```python
if _is_access_code_valid_for_lesson(slug, lesson_id, access_code):
    # --- NEW: session write ---
    lesson_ids = [item["id"] for item in _get_course_lessons(slug, course["title"])]

    if _is_skeleton_key(slug, access_code):
        # Unlock ALL lessons in the course
        unlocked_set = set(lesson_ids)
    else:
        unlocked_set = {lesson_id}

    session.setdefault("unlocked", {})
    existing = session["unlocked"].get(slug, set())
    session["unlocked"][slug] = existing | unlocked_set
    # --- end session write ---

    return redirect(url_for("lessons.lesson_page", slug=slug, lesson_id=lesson_id))
```

### 5.2 `GET /courses/<slug>/lessons/<int:lesson_id>` — `public_lesson_page()`

**Current:** Only serves **free** (non-restricted) lessons. Redirects to `/access` if restricted.  
**New:** Serves **both** free and unlocked-restricted lessons. If restricted and not unlocked, redirect to `/access`.

```python
@lesson_bp.get("/courses/<slug>/lessons/<int:lesson_id>")
def lesson_page(slug, lesson_id):
    # ... course + lesson validation (same as before) ...

    if lesson.get("hex"):
        if not _is_unlocked(slug, lesson_id):
            return redirect(url_for("lessons.lesson_access", slug=slug, lesson_id=lesson_id))
        # else: fall through to render

    content_html = _load_lesson_content(slug, lesson_id)
    return render_template("lesson_page.html", ...)
```

⚠️ **Note:** This route is currently named `public_lesson_page`. Rename it to `lesson_page` (the old `lesson_page` route at `/lessons/<hex_id>.html` will be deprecated — see §7).

### 5.3 `GET /lessons/<hex_id>.html` — `lesson_page()` (deprecated)

**Current:** Accepts a hex code in the URL path, resolves it to a lesson, renders content.  
**New:** Keep as a **backward-compatibility shim** that:
1. Validates the hex code.
2. On success, writes the unlock to session (same logic as §5.1).
3. Issues a **308 Permanent Redirect** to the clean URL `/courses/<slug>/lessons/<id>`.

```python
@lesson_bp.get("/lessons/<hex_id>.html")
def legacy_lesson_page(hex_id):
    hex_id = hex_id.lower()
    lesson_match = _resolve_lesson_by_code(hex_id)  # existing logic
    if not lesson_match:
        return render_template(...), 404

    course_slug, lesson_id = lesson_match
    # Grant session unlock (same as POST handler)
    _grant_unlock_in_session(course_slug, lesson_id, hex_id)

    return redirect(
        url_for("lessons.lesson_page", slug=course_slug, lesson_id=lesson_id),
        code=308,
    )
```

**Why 308:** Preserves the HTTP method (GET → GET) and signals to clients that the old URL is permanently superseded.

### 5.4 `GET /courses/<slug>/lessons/<int:lesson_id>/access` — `lesson_access()` (GET)

No change needed. Still renders the access code entry form.

### 5.5 `GET /courses/<slug>` — `course_detail()`

**Change:** Pass `unlocked` set to the template so the UI can indicate which lessons are already accessible.

```python
unlocked_lessons = session.get("unlocked", {}).get(slug, set())

return render_template(
    "course_detail.html",
    course=course,
    lessons=lessons,
    lessons_count=len(lessons),
    unlocked_lessons=unlocked_lessons,  # NEW
)
```

---

## 6. Template Changes

### `course_detail.html`

Add conditional rendering: if a lesson is in `unlocked_lessons`, change the button text / style.

```diff
 {% if lesson.hex %}
-  <a ...>REQUIRE ACCESS KEY</a>
+  {% if lesson.id in unlocked_lessons %}
+  <a href="{{ url_for('lessons.lesson_page', slug=course.slug, lesson_id=lesson.id) }}">VIEW LESSON</a>
+  {% else %}
+  <a ...>REQUIRE ACCESS KEY</a>
+  {% endif %}
 {% else %}
   <a ...>OPEN LESSON</a>
 {% endif %}
```

### `lesson_page.html`

No functional changes needed — the template already renders `entry` dict and `content_html`.  
The "ACCESS GRANTED" placeholder text could be updated to show "UNLOCKED" when accessed via session, but this is cosmetic.

### `lesson_access.html`

No changes needed — still shows the code entry form.

---

## 7. Migration / Backward Compatibility

| Old URL | Status | New URL |
|---------|--------|---------|
| `/courses/<slug>/lessons/<id>/access` (POST) | **Same** — session write instead of hex redirect | *(unchanged)* |
| `/courses/<slug>/lessons/<id>/access` (GET) | **Same** | *(unchanged)* |
| `/courses/<slug>/lessons/<id>` | **Enhanced** — now serves unlocked restricted lessons | *(unchanged)* |
| `/lessons/<hex_id>.html?...` | **Deprecated** — 308 redirect to clean URL | `/courses/<slug>/lessons/<id>` |

### Deprecation timeline

1. **Immediate:** Old hex-code URLs redirect via 308. All internal links are updated to the clean URL.
2. **N+1 release:** Add a warning log on legacy route hits.
3. **N+2 release:** Remove the legacy route. Document the breaking change.

### All internal link generation must use clean URLs

Search for every `url_for` and template `href` that generates a hex-code URL:

- `lessons.lesson_page` (with `hex_id`) → change to `lessons.lesson_page` (with `slug`, `lesson_id`)
- In `test_app.py`: assertions on `response.headers["Location"]` changing from `/lessons/<hex_id>.html?...` to `/courses/<slug>/lessons/<id>`

---

## 8. Security Considerations

### 8.1 Session cookie hardening

```python
app.config["SESSION_COOKIE_HTTPONLY"] = True          # not readable by JS
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"         # CSRF mitigation
app.config["SESSION_COOKIE_SECURE"] = True             # HTTPS only (production)
```

### 8.2 Session secret key

Ensure `app.secret_key` is set to a strong, unpredictable value:

```python
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")
```

In development the default is acceptable; in production it **must** be a long random string from environment.

### 8.3 Session size limits

Each lesson entry in the unlocked set is a small integer. For a course with 100 lessons:  
~800 bytes Python repr → ~1.2 KB serialized. Well within signed-cookie limits (4 KB) and negligible for filesystem/Redis.

### 8.4 Session fixation

Since there is no user login, session fixation is not a relevant threat. The session is anonymous and the unlocked set is additive-only — there is no privilege to escalate.

### 8.5 CSRF

The access POST handler mutates session state. Mitigations:
- `SameSite=Lax` on the session cookie prevents cross-site POST.
- Rate limiting (5 POST/min) limits brute-force and automated CSRF.
- A future improvement could add a per-session CSRF token, but this is not required for the initial implementation given `SameSite=Lax`.

### 8.6 What session-based access does NOT solve

- **Shared secrets still in plaintext** in `access.json` (Phase 2: hashing)
- **No user binding** — anyone who obtains a valid code can unlock their own session
- **No revocation** without clearing `access.json` and invalidating all sessions

These are tracked as Phase 2/3 items in `SECURITY.md`.

---

## 9. New Dependencies

### `Flask-Session` ≥0.8.0

```txt
# requirements.txt
flask-session>=0.8.0
```

Optional production backends:
```txt
redis>=5.0.0       # if using SESSION_TYPE=redis
```

### Implementation: `flask_session` vs `flask.sessions`

Use the third-party `Flask-Session` package (not `flask.sessions.SecureCookieSessionInterface`) because:
- It provides filesystem and Redis backends out of the box.
- It supports `SESSION_PERMANENT` and session lifetime config.
- It handles session ID generation and cookie management.
- If the null (signed cookie) backend is preferred, `flask.sessions` alone suffices, but `Flask-Session` is the recommended industry standard for Flask server-side sessions.

---

## 10. Helper Abstraction

Extract session logic into a new module `minilms/session_manager.py` to keep routes clean:

```python
"""Session-based unlock state management."""

from flask import session


def grant_unlock(course_slug: str, lesson_id: int) -> None:
    """Record a lesson as unlocked in the current session."""
    session.setdefault("unlocked", {})
    if course_slug not in session["unlocked"]:
        session["unlocked"][course_slug] = set()
    session["unlocked"][course_slug].add(lesson_id)


def grant_skeleton_unlock(course_slug: str, lesson_ids: list[int]) -> None:
    """Unlock all lessons in a course (skeleton key grant)."""
    session.setdefault("unlocked", {})
    session["unlocked"][course_slug] = set(lesson_ids)


def is_unlocked(course_slug: str, lesson_id: int) -> bool:
    """Check whether the current session has unlocked a specific lesson."""
    unlocked: dict[str, set[int]] = session.get("unlocked", {})
    return lesson_id in unlocked.get(course_slug, set())


def get_unlocked_lessons(course_slug: str) -> set[int]:
    """Return the set of unlocked lesson IDs for a course."""
    return session.get("unlocked", {}).get(course_slug, set())
```

---

## 11. Testing Strategy

### Tests to modify

| Existing test | Change |
|---|---|
| `test_access_flow_and_rendered_lesson` | Assert redirect to **clean URL** (`/courses/python-basics/lessons/1`), then follow it and assert 200 + content |
| `test_summary_lesson_can_be_restricted_via_access_json` | Same — clean URL in Location header |
| `test_any_code_in_lesson_code_list_unlocks_lesson` | Same — clean URL |
| `test_skeleton_key_unlocks_multiple_lessons` | Same — clean URL; also follow redirect and assert both lessons accessible |
| `test_valid_access_code_succeeds_under_threshold_with_rate_limit_enabled` | Clean URL assertion |
| `test_protected_lessons_still_require_access_key` | No change — still redirects to `/access` |

### Tests to add

| Test | What it verifies |
|---|---|
| `test_session_persists_unlock_across_requests` | POST code → follow redirect → assert 200. Second request to same lesson (without code) → assert 200. |
| `test_locked_lesson_redirects_to_access_form` | GET on locked lesson without session → 302 to `/access`. |
| `test_skeleton_key_unlocks_all_lessons_in_session` | POST skeleton key → assert all lesson IDs in session for that course are unlocked |
| `test_legacy_hex_url_redirects_and_grants_session` | GET `/lessons/<hex_id>.html?...` → 308 → session has unlock → follow redirect to clean URL = 200 |
| `test_session_does_not_leak_across_courses` | Unlock lesson in course A → course B still locked |
| `test_invalid_hex_code_legacy_url_returns_404` | GET `/lessons/badcode.html` → 404 |
| `test_unlocked_set_in_template` | POST code → GET course detail → assert lesson button shows "VIEW LESSON" not "REQUIRE ACCESS KEY" |

### Test helpers

```python
from flask import session

# Within a test, after client POST:
with client.session_transaction() as sess:
    assert 1 in sess["unlocked"]["python-basics"]
```

### Session fixture for tests

```python
@pytest.fixture(autouse=True)
def session_test_config(monkeypatch):
    """Use signed-cookie (null) backend in tests for simplicity."""
    monkeypatch.setitem(app.app.config, "SESSION_TYPE", "null")  # or "filesystem"
```

---

## 12. Implementation Checklist

### Step 1: Add dependency

- [ ] Add `flask-session>=0.8.0` to `requirements.txt`
- [ ] `pip install flask-session`

### Step 2: Create session manager module

- [ ] Create `minilms/session_manager.py` with `grant_unlock()`, `grant_skeleton_unlock()`, `is_unlocked()`, `get_unlocked_lessons()`

### Step 3: Configure Flask-Session in app.py

- [ ] Import `flask_session.Session`
- [ ] Set `SESSION_TYPE`, `SESSION_FILE_DIR`, `SESSION_PERMANENT`, `PERMANENT_SESSION_LIFETIME`, `SESSION_USE_SIGNER`, `SESSION_COOKIE_*` config
- [ ] Call `Session(app)` after config is set
- [ ] Set `app.secret_key` (from env or fallback)

### Step 4: Update routes/lessons.py

- [ ] In `lesson_access()` POST handler: on valid code, call `grant_unlock()` or `grant_skeleton_unlock()`, then redirect to `url_for("lessons.lesson_page", slug=..., lesson_id=...)`
- [ ] In `public_lesson_page()`: check `is_unlocked()` for restricted lessons; if locked, redirect to `/access`; if unlocked, render content
- [ ] Rename `public_lesson_page` endpoint to `lesson_page` (update `@lesson_bp.get` decorator and function name)
- [ ] Update `lesson_page()` at `/lessons/<hex_id>.html`: add `grant_unlock()` call, change redirect to 308 to clean URL
- [ ] Inject `_is_unlocked` / `_grant_unlock` wrappers through `app.config["MINILMS_*"]` or import `session_manager` directly

### Step 5: Update templates

- [ ] `course_detail.html`: accept `unlocked_lessons` set, conditionally render button text/link

### Step 6: Update wiring in routes/__init__.py and app.py

- [ ] Pass any new dependencies for the session-aware helpers
- [ ] Remove `_find_lesson_by_access_code` and `_is_access_code_valid_for_lesson` from DI if no longer needed by routes (now only used in legacy shim)

### Step 7: Update tests

- [ ] Update all redirect assertion tests to expect clean URL
- [ ] Add new tests from §11
- [ ] Add `session_test_config` fixture
- [ ] Run `python -m pytest -q` — all green

### Step 8: Manual smoke test

- [ ] Start app, visit a free course → lesson renders directly
- [ ] Visit a restricted lesson → shows access form
- [ ] Submit wrong code → error shown
- [ ] Submit correct code → redirect to clean URL → lesson renders
- [ ] Refresh lesson page → still renders (session persisted)
- [ ] Close browser, reopen → session lost (if not permanent) → lesson locked again
- [ ] Old hex-code URL → 308 redirect → lesson renders
- [ ] Course detail page shows "VIEW LESSON" for unlocked lessons

### Step 9 (deprecation tracking)

- [ ] Add `current_app.logger.warning("legacy hex-code URL accessed: ...")` in the legacy route
- [ ] Optionally, set a deprecation header: `response.headers["Deprecation"] = "true"`

---

## 13. Files Changed Summary

| File | Action |
|------|--------|
| `requirements.txt` | Add `flask-session>=0.8.0` |
| `app.py` | Import + init `Session`; add config; set `secret_key` |
| `minilms/session_manager.py` | **New** — unlock state helpers |
| `minilms/routes/lessons.py` | Rewrite access POST, lesson GET, legacy shim |
| `minilms/routes/__init__.py` | Possibly remove unused DI entries |
| `minilms/routes/courses.py` | Pass `unlocked_lessons` to template |
| `templates/course_detail.html` | Conditional button per unlock state |
| `tests/test_app.py` | Update redirect assertions + new session tests |

---

## 14. Future Considerations (not in scope)

- **Access code hashing** (`CRITICAL.md` §3.1): After this migration, the next security step is to hash codes with `argon2` so that a leaked `access.json` does not expose plaintext keys.
- **Redis session backend for multi-worker deployments**: Document `SESSION_TYPE=redis` with `SESSION_REDIS` URI.
- **Session invalidation endpoint**: A `POST /logout` that clears `session["unlocked"]` (or calls `session.clear()`).
- **Persistent unlock across browser restarts**: Increase `PERMANENT_SESSION_LIFETIME` or use "remember me" checkbox on the access form.
