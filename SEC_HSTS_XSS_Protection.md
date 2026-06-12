# Specification: Security Headers Rollout (HSTS & XSS Protection)

Author: Software Architect (Banking & Security)
Status: Implemented (application middleware + deployment guidance)
Priority: High (Critical for Production)
Target: MiniLMS Flask deployment
Date: 2026-06-10

## 1. Analysis of Current State

Current application posture (observed):
- Rate limiting is implemented in application layer (Flask-Limiter).
- No security-header middleware is currently configured in application code.
- Markdown is rendered to HTML and returned to templates, which increases the importance of CSP and defense-in-depth headers.

Gap summary:
- Missing mandatory production headers at response boundary.
- Missing HTTPS enforcement policy (HSTS) at the edge.
- Missing explicit referrer, MIME-sniffing, and clickjacking controls.

## 2. Implementation Decision

Implemented in MiniLMS with lightweight application middleware (no extra dependency beyond Flask stack), while keeping edge-layer guidance for production parity.

Benefits:
- Low dependency footprint (no Flask-Talisman required).
- Works in local/staging environments without separate proxy configuration.
- Can be mirrored at reverse proxy/WAF for defense in depth.

Tradeoff:
- CSP nonces/hashes are not yet implemented; current policy is static and should be tightened iteratively.

## 3. Required Header Baseline

Apply these headers in production HTTPS responses:

| Header | Required Value | Notes |
| :--- | :--- | :--- |
| Strict-Transport-Security | max-age=31536000; includeSubDomains | Set only on HTTPS responses |
| Content-Security-Policy | default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'self' | Start here, then remove 'unsafe-inline' once templates/styles permit |
| X-Frame-Options | SAMEORIGIN | Clickjacking protection |
| X-Content-Type-Options | nosniff | MIME-sniff prevention |
| Referrer-Policy | strict-origin-when-cross-origin | Limits referer leakage |
| X-XSS-Protection | 1; mode=block | Legacy browser compatibility |

## 4. Edge-Layer Implementation

### 4.1 Nginx (recommended for self-hosted rollout)

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    # ... ssl_certificate / ssl_certificate_key ...

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4.2 Cloudflare/WAF equivalent

If using managed edge, configure equivalent response header transform rules:
- Add each header/value from Section 3.
- Restrict to production hostnames.
- Enable HTTPS redirection before enabling long-lived HSTS.

## 5. Rollout Strategy

1. Stage first with full headers and CSP report review.
2. Validate app rendering and lesson pages (including markdown-heavy pages).
3. Deploy production with same header set.
4. After 7 days of stability, consider adding `preload` to HSTS only if domain policy allows it.

## 6. Verification Steps

Run from a terminal against staging/production hostname:

```bash
curl -I https://example.com/
```

Expected presence:
- Strict-Transport-Security
- Content-Security-Policy
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy
- X-XSS-Protection

Browser checks:
- Open DevTools Console for CSP violations.
- Visit course list, restricted lesson flow, public lesson flow.
- Confirm no blocked first-party CSS/JS assets.

## 7. Security Validation Checklist

- [ ] HSTS max-age is at least 31536000 and only served over HTTPS.
- [ ] CSP has no wildcard source (`*`) and no `unsafe-eval`.
- [ ] Frame embedding is restricted (`SAMEORIGIN` and/or `frame-ancestors`).
- [ ] No MIME-sniffing on assets (`nosniff`).
- [ ] Referrer policy is active on all HTML responses.
- [ ] Regression pass on course navigation and lesson rendering.

## 8. Opinion

This is the right security direction, but application-level `Flask-Talisman` is optional if edge controls are consistently enforced. For MiniLMS, the best immediate move is edge-enforced headers now, followed by markdown sanitization and authentication redesign next. In other words: this specification is strong, and implementing it at the proxy is the fastest, safest path that respects the no-code constraint.
