# Security Policy & Audit

This document outlines the security posture of MiniLMS, identifies known risks, and provides a roadmap for production readiness.

## Reporting a Vulnerability
If you discover a security vulnerability within this project, please do not open a public issue. Instead, contact the maintainer directly.

## 1. Security Audit (June 2026)

The current application is a prototype that utilizes **obfuscation rather than robust authorization**.

| Category | Finding | Impact | Status |
| :--- | :--- | :--- | :--- |
| **Authentication** | Shared static hex codes. Transferable and leak-prone. | **High** | ⚠️ Known Risk |
| **Session Mgmt** | Access granted via URL (`/lessons/<hex_id>.html`). Easily cached/indexed. | **Medium** | ⚠️ Known Risk |
| **Rate Limiting** | Flask-Limiter enforced globally and with strict policy on `/access` POST (5/minute, 20/hour per IP+route). | **Medium** | ✅ Implemented |
| **Content Security** | Filesystem reads based on slugs. | **Low** | ✅ Validated |
| **XSS** | Security headers enforced (CSP + frame/mime/referrer/XSS response headers); markdown sanitization still pending. | **Medium** | ⚠️ Partially Mitigated |
| **Infrastructure** | `debug=True` in main block. | **High** | ⚠️ Known Risk |

Rate limiting implementation details (2026-06-10):
- Global limits: `120/hour` and `30/minute` per IP.
- Access submission limits: `POST /courses/<slug>/lessons/<id>/access` limited to `5/minute` and `20/hour` per IP+route.
- Environment controls: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_STORAGE_URI`, `RATE_LIMIT_GLOBAL_HOURLY`, `RATE_LIMIT_GLOBAL_MINUTE`, `RATE_LIMIT_ACCESS_POST_MINUTE`, `RATE_LIMIT_ACCESS_POST_HOURLY`.
- Centralized HTTP 429 handling with retry guidance and `Retry-After` support.
- Residual production risk: use Redis storage and verify proxy trust chain in staging for multi-worker consistency.

## 2. Deployment Roadmap

### Phase 1: Security Hardening (Immediate)
*   **Rate Limiting**: ✅ Implemented via `Flask-Limiter` (global + strict `/access` POST policy).
*   **Rate Limiting Production Validation**: Configure Redis backend and validate forwarded IP trust chain under reverse proxy.
*   **Production Server**: Transition to Gunicorn/Uvicorn; disable `debug=True`.
*   **Security Headers**: ✅ Implemented with lightweight in-app middleware (HSTS on HTTPS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, X-XSS-Protection).
*   **Error Handling**: ✅ Implemented custom 404/500 pages to avoid leaking system internals.

### Phase 2: User Persistence (Short-term)
*   **Session-based Access**: Use `Flask-Session` to store "unlocked" state in secure cookies rather than exposing keys in URLs.
*   **Database Migration**: Move `access.json` to SQLite for concurrency and audit logging.
*   **Sanitization**: Implement `bleach` to sanitize Markdown-to-HTML output.

### Phase 3: Identity & Distribution (Mid-term)
*   **Personal Tokens**: Replace shared keys with unique, user-bound tokens.
*   **Identity**: Add "Email Magic Links" for lightweight user authentication.
*   **Admin Tools**: Build a simple interface to generate, track, and revoke access keys.

### Phase 4: Monitoring & Scale (Production)
*   **CI/CD**: Automate tests and security scanning in GitHub Actions.
*   **Audit Logging**: Log token usage and IP patterns for abuse detection.
*   **Cloud Deployment**: Move to a containerized (Docker) environment with centralized logging.

## 3. Hexkey Distribution Strategy

To distribute access keys to users, the following methods are recommended:

*   **Option A: Automated Email (Recommended)**: A `/request-access` page where users enter their email to receive a unique key generated via `secrets.token_hex(8)`.
*   **Option B: Batch CSV Generation**: Use a script to generate 100+ unique keys, which are then manually imported into an email marketing tool (e.g., Mailchimp).
*   **Option C: E-commerce Webhooks**: Integrate with Gumroad or LemonSqueezy to automatically trigger key generation and delivery upon a successful purchase/signup.

## 4. Current Posture Summary

MiniLMS is currently suitable for **internal demos, early-stage prototypes, and free content**. Baseline request throttling is now in place, but the project is still NOT recommended for paid or sensitive content until production deployment hardening (Redis-backed limiter, proxy validation, secure runtime configuration) and Phase 2 controls are implemented.
