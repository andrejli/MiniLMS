# NEXT: Repository Analysis and Opinion

Date: 2026-06-04

## Opinion in one line
This is a strong prototype for a minimalist LMS, but it is still a prototype: clear and easy to extend, yet missing production-level security boundaries and structural separation.

## What is working well
- The app is small and understandable end-to-end (`app.py` + a few templates).
- Content is file-driven (`content/lessons/...`) which is great for fast authoring and portability.
- Routing flow is coherent: course list -> course detail -> lesson access -> lesson page.
- Existing tests cover key behavior (course discovery, successful unlock flow, invalid code 404).
- The visual identity is distinct and memorable (PIP-Boy theme), not generic boilerplate.

## Key risks and weaknesses

### 1) Access control is obfuscation, not authorization
- Lesson access relies on shared static hex codes.
- Codes are reusable and transferable; no user binding, expiry, rate limiting, or audit trail.
- Suitable for demos or low-risk content, not suitable for paid/private learning content.

### 2) Monolithic backend file
- Most logic lives in `app.py`.
- This is fine now, but will become hard to maintain once you add accounts, payments, progress tracking, or more courses.

### 3) Frontend assets include likely dead or mismatched features
- Status: largely resolved.
- Dead cart/checkout/privacy CSS was removed and `static/js/security.js` was removed from the active app flow.
- Residual risk: keep CSS aligned with templates as features evolve.

### 4) CSS structure issue likely present
- Status: resolved.
- Media-query brace structure was corrected and responsive rendering was verified across breakpoints.

### 5) Test coverage is narrow for future changes
- Current tests are good smoke tests, but they do not cover:
  - malformed markdown or missing lesson files
  - unknown course/lesson access pages in detail
  - HTML escaping/sanitization expectations
  - security boundaries (brute force/rate limiting behavior)

## Priority roadmap

## Progress update (completed)
- Completed: fixed CSS media-query brace structure and verified responsive behavior.
- Completed: removed dead frontend features not used by templates (`security.js`, cart/checkout/privacy CSS blocks).
- Completed: moved hard-coded access code map to `access.json` and updated app validation to read from JSON.
- Completed: added a free course with public lessons and no key requirement.

## P0 (do next)
1. [DONE] Fix CSS media-query brace structure and verify responsive rendering.
2. [DONE] Remove dead CSS/JS features not used by current templates, or wire them up intentionally.
3. Add tests for error paths and content edge cases (missing lesson file, invalid lesson id, empty content).
4. [DONE] Move hard-coded hex route map to a data file or environment-backed config.

## P1 (near-term)
1. Split backend into modules:
   - content loading
  - routing
   - access policy
2. Add a minimal app factory pattern for easier testing and future config profiles.
3. Add basic request logging and explicit error handlers for 404/500 templates.
4. Tighten dependency pinning (direct runtime deps explicit in requirements).

## P2 (if aiming for real users)
1. Replace shared access codes with one-time or user-bound tokens.
2. Add rate limiting on access endpoint.
3. Add simple audit logging (token usage, timestamp, source IP).
4. Add basic identity (email magic link or lightweight auth).

## Suggested architecture direction
- Keep markdown file-based lessons (good constraint).
- Add a thin domain layer around:
  - `CourseRepository` (filesystem today, DB tomorrow)
  - `AccessService` (validation/issuance policy)
  - `LessonRenderer` (markdown + sanitization policy)
- Keep Flask routes as orchestration only.

## Final recommendation
Continue with this repository. It is a good foundation for a "small LMS" strategy, but do not scale features on top of the current access model and single-file backend. First harden boundaries, then modularize, then expand product features.
