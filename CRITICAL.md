# Critical Architectural & Security Review: MiniLMS

**Reviewer:** Gemini CLI (CyberSec & Software Architecture)  
**Date:** June 12, 2026  
**Final Grade:** **C- (Functional Prototype / Production-Fragile)**

---

## 1. Security Analysis (The "House of Cards")

### 1.1 Fatal Flaw: Security through Obscurity (Hex URLs)
The application redirects authorized users to `/lessons/<hex_id>.html`. 
*   **Risk:** The `hex_id` (the secret) is leaked in browser history, server logs, and HTTP referer headers.
*   **Impact:** High. Any user who bookmarks or shares this URL bypasses the access control mechanism entirely. There is no server-side session validation.

### 1.2 Authentication Weakness
*   **Shared Secrets:** Access codes are shared secrets, not user-specific identities. There is no revocation mechanism, no audit trail of who accessed what, and no protection against credential stuffing beyond basic rate limiting.
*   **Plaintext Secrets:** `access.json` stores codes in plaintext. A single misconfiguration or local file inclusion (LFI) vulnerability exposes the entire content library.

### 1.3 Denial of Service (DoS) Vectors
*   **CPU Exhaustion:** Markdown rendering is performed synchronously on every request. An attacker can spam requests to complex lesson pages to pin the CPU, as there is no HTML-level caching.
*   **I/O Blocking:** The app performs multiple disk scans (`Path.glob`) and reads per request. This blocks the Python event loop, leading to rapid degradation under even moderate concurrency.

---

## 2. Maintenance & Technical Debt

### 2.1 The "Filesystem as a Database" Anti-Pattern
Relying on specific filename patterns (`lesson-N.md`) and directory structures for business logic is brittle.
*   **Regex Fragility:** `LESSON_FILENAME_RE` will ignore valid content that doesn't fit the exact naming convention, leading to "hidden" content bugs.
*   **No Content Integrity:** There is no schema validation for content. A typo in a filename or a malformed JSON entry in `access.json` can crash the routing engine.

### 2.2 Brittle Routing
The `register_routes` pattern (manually injecting 10+ functions) makes the application nearly impossible to extend without massive merge conflicts and cognitive load.

### 2.3 Environment Instability
*   **Test Reliance:** The project lacks a robust, auto-installing test environment (e.g., a locked `requirements.txt` or `tox` config). Tests failed to run in the current environment due to missing dependencies.

---

## 3. Remediation Roadmap (Prioritized)

### 3.1 Immediate (P0: Security)
*   **DEPRECATE Hex URLs:** Move to session-based or JWT-based authorization. The URL should be clean (e.g., `/course/slug/lesson/1`), and the server must verify the session on every request.
*   **Hash Access Codes:** Use `scrypt` or `Argon2` to store hashes in `access.json`, not the codes themselves.

### 3.2 Short-Term (P1: Architecture)
*   **Implement I/O Caching:** Use `lru_cache` or a singleton to store the course manifest in memory. Stop scanning the disk on every request.
*   **Modularize via Blueprints:** (See `OPT_BLUEPRINTS.md`) to decouple routing from the app entry point.

### 3.3 Strategic (P2: Scalability)
*   **Transition to Database:** Migrate from `access.json` and filesystem scanning to a relational database (SQLite/PostgreSQL).
*   **Asynchronous Content Loading:** Use background tasks or pre-rendering for Markdown-to-HTML conversion.

---

## 4. Final Verdict
MiniLMS is a well-written **Personal Wiki**, but it is currently **unfit for public-facing educational use**. The lack of true session management and the exposure of secrets in URLs are "Stop Ship" issues for any security-conscious deployment.
