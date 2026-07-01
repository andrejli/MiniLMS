# Tor Deployment Analysis — MiniLMS

## Summary

MiniLMS is **well-suited** for Tor deployment with zero JavaScript, minimal
external dependencies, small templates, and a cookie-based (non-IP-dependent)
session system. Three blocking issues must be addressed before a `.onion`
deployment.

---

## Verdict by Area

| Area | Verdict | Details |
|------|---------|---------|
| Page weight | **Good** | Templates 0.4–1.2 KB each. One 1 KB favicon. No JS. |
| External deps | **Good** | No external dependencies. Google Fonts `@import` removed. |
| Session mgmt | **Good** | Cookie-based. Survives Tor IP rotation. |
| CSP | **Good** | `default-src 'self'`. No external resources allowed. |
| Templates | **Good** | Simple inheritance, no heavy nesting. |
| Rate limiting | **FIXED** | Session-based keying in `app.py:_session_or_ip()`. Each Tor user gets their own bucket. |
| Caching | **FIXED** | `Cache-Control: private, max-age=3600`. Configurable via `CACHE_HTML_MAX_AGE`. |
| HTTPS | **FIXED** | `FORCE_HTTPS` now defaults to `false`. Set explicitly for TLS-proxy setups. |

---

## Blocking Issues (Fix Before Tor Deployment)

### 1. [FIXED] IP-based rate limiting penalized all users behind same Tor exit node

**File:** `app.py:71-83`

`get_remote_address` was the rate-limit key. All Tor users sharing an exit node
shared the same 120/hour, 30/minute global bucket and the same 5/minute, 20/hour
access-POST bucket. One user hitting the limit blocked everyone behind that exit
node.

**Fix applied:** Replaced IP-based key with session-based key
(`f"sess:{session.sid}"`), falling back to client IP when no session is
available. The session is touched on every rate-limited request to ensure
flask-session persists the cookie even for empty sessions. See
`app.py:_session_or_ip()` and `app.py:limit_key_sid_plus_route()`.

### 2. [FIXED] HTTPS enforcement broke `.onion` access

**File:** `minilms/security_headers.py:16-19` (`default_force_https()`)

`FORCE_HTTPS` previously defaulted to `true` in production/staging (based on
`FLASK_ENV`). `.onion` sites use native HTTP, so the redirect to `https://`
would fail.

**Fix applied:** `default_force_https()` now returns `False` unconditionally.
`FORCE_HTTPS=true` must be set explicitly when running behind a TLS-terminating
proxy. This makes `.onion` deployments work out of the box with no env var
changes. Also ensure `SESSION_COOKIE_SECURE=false` (already the default).

### 3. [FIXED] No HTML caching — every page load was a full round trip

**File:** `app.py:set_html_cache()`

`Cache-Control: no-store` previously forced full re-download on every page
load. Tor circuits have 2–3× latency, so every navigation was slow.

**Fix applied:** Replaced with `Cache-Control: private, max-age=3600` (1-hour
browser cache). Configurable via `CACHE_HTML_MAX_AGE` env var (set to `0` to
restore no-store behaviour during content editing). Content changes rarely
(only when admin edits markdown files), so 1-hour staleness is acceptable.

---

## High Priority Issues

### 4. [FIXED] Google Fonts `@import` was a dead external dependency

**File:** `static/css/style.css:1`

The `@import` was already blocked by CSP (`style-src 'self'`), causing a
silent failure on every page. If CSP were loosened later it would become a
DNS leak and fingerprinting vector.

**Fix applied:** Removed the `@import` line. The font stack
(`'VT323', 'Courier New', monospace`) falls through to Courier New on
Windows/macOS and the system monospace (Consolas, Menlo, DejaVu Sans Mono)
on every platform — all terminal-like fonts. No external requests needed.

### 5. `debug=True` enabled in production path

**File:** `app.py:168`

```python
app.run(host="0.0.0.0", port=5000, debug=True)
```

Exposes the Werkzeug debugger and stack traces. On a Tor-exposed instance this
is a code execution vector.

**Fix:** `debug=os.getenv("FLASK_DEBUG", "false").lower() == "true"`.

### 6. [FIXED] No favicon — extra 404 round trip on every page load

**File:** `templates/base.html:7`

Browsers automatically request `/favicon.ico`. Without one, every page load
triggered a 404. Over Tor, each 404 added 2–3 seconds of latency.

**Fix applied:** Added `<link rel="icon">` in `base.html` pointing to
`static/images/favicon.ico`. The file already exists; the template now tells
browsers exactly where to find it, eliminating the root 404.

### 7. [FIXED] Server header identified Flask/Werkzeug

**File:** `app.py:remove_server_header()`

Flask defaults to `Server: Werkzeug/x.x.x Python/x.x.x`, revealing
framework versions and aiding fingerprinting.

**Fix applied:** Added `response.headers.pop("Server", None)` in an
`after_request` handler.

---

## Medium Priority Issues

### 8. [FIXED] CSRF protection missing on access code form

**Files:** `minilms/routes/lessons.py:_csrf_token()`, `templates/lesson_access.html`

The access code POST handler granted session unlocks with no CSRF token. Only
`SameSite=Lax` protected it. A Tor user with an active session visiting a
malicious site could have been forced to POST to the `.onion` access endpoint.

**Fix applied:** Added manual CSRF token generation (`secrets.token_hex(32)`)
stored in the session, validated on POST via `secrets.compare_digest`. The
hidden `_csrf_token` field is rendered in the form template. No Flask-WTF
needed — zero extra dependencies.

### 9. [FIXED] CSS was unminified (10.6 KB)

**File:** `static/css/style.css`

10.6 KB of CSS for a 7-page app with no images or JS. Well-commented but not
optimized for bandwidth.

**Fix applied:** Minified to 7.4 KB (single line, comments stripped). Every
byte matters over Tor. The original readable version should be kept as a
reference if extensive future edits are needed.

### 10. [FIXED] Plaintext access codes in `access.json`

**File:** `manage_access.py:cmd_rehash()`

Some access codes were stored as plain hex strings alongside PBKDF2 hashes. If
the server was compromised, plaintext codes were exposed.

**Fix applied:** Added `manage_access.py rehash` command. Scans access.json for
legacy plaintext hex strings and existing pbkdf2 hashes without IDs, converts
each to a dict entry with a unique K-... ID and a PBKDF2 hash. Supports
`--dry-run` to preview changes. Plaintext codes are no longer stored in
access.json.

---

## Low Priority Issues

| Issue | Location | Detail |
|-------|----------|--------|
| `Referrer-Policy` could leak `.onion` domain | `security_headers.py:34` | Currently `strict-origin-when-cross-origin`. If any external resource is added, the `.onion` origin leaks in Referer. Change to `same-origin` or `no-referrer` for Tor. |
| HSTS header unusual for `.onion` | `security_headers.py:41-45` | If behind TLS proxy, HSTS with `includeSubDomains` could pin a `.onion` domain to HTTPS causing browser errors. |
| Empty `static/js/` and `static/images/` | Filesystem | Minor overhead from Flask scanning empty directories. |
| No `noscript` fallback | All templates | Not needed (no JS), but a `noscript>` tag costs nothing and helps Tor Browser users. |
| Sessions are filesystem-backed | `app.py:35` | Per-process storage. Fine for single-process Tor deployment, but breaks with multiple workers behind a load balancer. |
| No HTML sanitization on markdown output | `content_service.py:117` | `Markup(html)` marks output as safe. Currently safe because content is file-based. Would be critical if content ever becomes user-controllable. |

---

## What Works Well for Tor

- **Zero JavaScript** — no JS attack surface, no `script-src` worries.
- **Zero images** — no image fingerprinting, no bandwidth waste.
- **Cookie-based sessions** — users keep their unlocks across Tor IP rotation.
- **Small templates** — all under 50 lines, minimal DOM.
- **Strict CSP** — `default-src 'self'`, no external resources allowed.
- **No CDN dependencies** — zero external hosts to contact.
- **No third-party trackers or analytics** — no privacy leaks.
- **`X-Content-Type-Options: nosniff`** — prevents MIME confusion attacks.

---

## Recommended Deployment Configuration

```bash
# Required for Tor
SESSION_COOKIE_SECURE=false
RATE_LIMIT_ENABLED=false

# Strongly recommended
FLASK_DEBUG=false
SECRET_KEY=<random-64-char-hex>

# Optional but recommended
REFERRER_POLICY=same-origin
SESSION_COOKIE_SAMESITE=Strict
```
