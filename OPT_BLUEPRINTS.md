# Specification: Refactoring to Flask Blueprints

**Architect:** Gemini CLI (CyberSec & Software Architecture)  
**Status:** Approved for Implementation  
**Priority:** High (Foundation for Scale)

## 1. Executive Summary
The current route registration in `app.py` uses a manual dependency injection pattern that is brittle and scales poorly. This specification directs the migration to **Flask Blueprints**. The goal is to decouple the application entry point from the routing logic, improve code discoverability, and simplify the injection of security middleware (like rate limiting).

## 2. Architectural Requirements

### 2.1 Minimalist Design
*   **No Logic Bloat:** Blueprints must only handle HTTP concerns (request parsing, routing, response rendering). Business logic remains in `minilms/content_service.py` and `minilms/access_control.py`.
*   **Accessing Config/Services:** Use `from flask import current_app` inside route functions to access app-level configuration. Do NOT pass the `app` object into Blueprint functions.

### 2.2 Logical Structure
Routes shall be partitioned into three distinct Blueprints:

1.  **`core_bp`**: `minilms/routes/core.py` (Home page, Global Error handlers).
2.  **`course_bp`**: `minilms/routes/courses.py` (Course discovery and detail).
3.  **`lesson_bp`**: `minilms/routes/lessons.py` (Lesson content, access control, and hex-code lookups).

### 2.3 Directory Layout
```text
minilms/
├── routes/
│   ├── __init__.py      # Blueprint aggregation and registration export
│   ├── core.py          # core_bp: name="core"
│   ├── courses.py       # course_bp: name="courses"
│   └── lessons.py       # lesson_bp: name="lessons"
```

---

## 3. Implementation Details (The "Dumb-Resistant" Guide)

### 3.1 Avoiding Circular Imports (CRITICAL)
**The Trap:** Importing `app` from `app.py` into `routes/core.py` while `app.py` imports `core_bp`. This will crash the app on startup.
**The Fix:** 
1.  Define the `Blueprint` object at the top of the route file.
2.  Import services (`content_service`, `access_control`) directly.
3.  Use `current_app` or Blueprint-local decorators.

### 3.2 URL Namespacing (The "Template Breaker")
**The Trap:** Once moved to a Blueprint named `courses`, `url_for('home')` becomes `url_for('core.home')`.
**The Fix:** You MUST update every `url_for` call in:
*   Python files (redirects).
*   HTML templates (`templates/*.html`).
*   **Rule:** If the Blueprint name is `lessons`, the route `lesson_page` is now `lessons.lesson_page`.

### 3.3 Rate Limiter Injection
**The Trap:** The `limiter` instance is created in `app.py`. How do Blueprints use it without importing `app`?
**The Fix:** 
In `app.py`, you can pass the `limiter` to a registration function, or better, use the `@limiter.limit` decorator by importing the limiter instance from a shared "extensions" file (though for now, passing it to a registration helper is fine).

---

## 4. Phase-by-Phase Execution

### Phase 1: The Core Infrastructure
1.  Create `minilms/routes/__init__.py`.
2.  Create `core.py`, `courses.py`, and `lessons.py`.
3.  In each file, initialize the Blueprint: `core_bp = Blueprint('core', __name__)`.

### Phase 2: Surgical Code Migration
1.  **Move routes 1-for-1.** Do not "optimize" or "improve" the code while moving it.
2.  Change `@app.get` to `@core_bp.get`.
3.  Replace all local variables like `get_courses` with direct imports: `from minilms.content_service import get_courses`.

### Phase 3: Global Search & Replace (The Verification Phase)
1.  **Search for `url_for`** across the entire project.
2.  Update all calls to include the blueprint prefix.
    *   `url_for('home')` -> `url_for('core.home')`
    *   `url_for('course_detail', ...)` -> `url_for('courses.course_detail', ...)`
    *   `url_for('lesson_page', ...)` -> `url_for('lessons.lesson_page', ...)`

---

## 5. Developer Checklist (Must all be Checked)
- [ ] **No Circular Imports:** I have NOT imported `app` from `app.py` in any route file.
- [ ] **Absolute Imports:** I used `from minilms.content_service import ...` and not `import content_service`.
- [ ] **Template Audit:** I have updated every `url_for` in the `/templates` folder.
- [ ] **Error Handlers:** The `429` handler is now `@core_bp.app_errorhandler(429)` (so it remains global).
- [ ] **Tests Pass:** I ran `pytest` and it shows green.
- [ ] **Manual Verification:** I can successfully enter an access code and be redirected to a lesson.

## 6. If it Fails...
1.  **"AttributeError: 'NoneType' object has no attribute 'name'":** You likely have a circular import.
2.  **"BuildError: Could not build url for endpoint 'home'":** You forgot to add the `core.` prefix in a template or redirect.
3.  **"Limiter not working":** Check if you passed the `limiter` correctly during registration or if the decorator is applied to the blueprint function.
