# MiniLMS Rate Limiting Development Specification

## Document Control
- Owner: Security/Backend
- Status: Ready for implementation
- Last updated: 2026-06-09
- Related risk register: `SECURITY.md` (Rate Limiting marked High)

## 1. Problem Statement
MiniLMS has an access-code gate on:

- `GET|POST /courses/<slug>/lessons/<int:lesson_id>/access`

Current behavior allows unlimited POST attempts with arbitrary keys. This creates:

- Brute-force and enumeration risk against lesson access codes.
- Denial-of-service risk due to repeated requests.
- Operational instability when traffic spikes are malicious.

## 2. Scope

### In scope
- Request throttling for all routes (baseline protection).
- Strict throttling for access-code submission route (POST only).
- Consistent error behavior for throttled requests.
- Production-safe deployment guidance (proxy and shared state).
- Test plan and acceptance criteria.

### Out of scope
- Replacing access codes with user authentication.
- Captcha rollout (listed as an optional control).
- Full WAF rollout (listed as an alternative architecture).

## 3. Security Objectives

### Primary objectives
- Reduce automated invalid code attempts by at least 95% in burst traffic tests.
- Preserve service availability under moderate abusive traffic.
- Avoid global lockout of legitimate users behind shared NAT where possible.

### Non-functional requirements
- P95 additional latency from limiter check: less than 10 ms with Redis backend.
- No functional regression in valid access-code flow.
- Rate-limit behavior consistent across multi-worker deployments.

## 4. Proposed Baseline Architecture (Application Layer)

Use Flask-Limiter with Redis-backed counters in production.

### Identity keying strategy
- Primary key: client IP (trusted proxy chain required in production).
- Optional hardening key: IP plus route for endpoint-specific budgets.

### Limit policy

| Policy | Applies To | Limit | Response |
| :--- | :--- | :--- | :--- |
| Global hourly | All routes | 120/hour per IP | 429 |
| Global burst | All routes | 30/minute per IP | 429 |
| Access POST burst | `/courses/<slug>/lessons/<id>/access` POST | 5/minute per IP+route | 429 |
| Access POST sustained | same as above | 20/hour per IP+route | 429 |

Notes:
- Keep status code as 429 for all throttling to preserve HTTP semantics.
- Do not return 403 for temporary throttles; reserve 403 for authorization failures.

## 5. Implementation Plan (No code in this document)

### Phase 1: Dependency and bootstrap
- Add Flask-Limiter dependency to project requirements.
- Initialize limiter during app startup.
- Configure default limits (global) and route-specific limits.

### Phase 2: Route policy enforcement
- Apply stricter limits to POST submissions on lesson access endpoint.
- Ensure GET page render is either exempt or less strict than POST.

### Phase 3: Error handling and UX
- Define centralized handler for 429.
- Return user-safe message and retry guidance (for example, try again in 60 seconds).
- Include `Retry-After` header where available.

### Phase 4: Production hardening
- Enable proxy trust settings so client IP is accurate behind reverse proxy.
- Use Redis storage URI in production.
- Verify same behavior across multiple workers and instances.

### Phase 5: Monitoring and rollout
- Add logs/metrics for throttled events by endpoint and source.
- Roll out limits in conservative mode first, then tighten if needed.
- Review metrics after 7 days and recalibrate thresholds.

## 6. Configuration Specification

### Environment keys
- `RATE_LIMIT_ENABLED`: `true|false`
- `RATE_LIMIT_STORAGE_URI`: `memory://` for local dev, Redis URI for production
- `RATE_LIMIT_GLOBAL_HOURLY`: default `120/hour`
- `RATE_LIMIT_GLOBAL_MINUTE`: default `30/minute`
- `RATE_LIMIT_ACCESS_POST_MINUTE`: default `5/minute`
- `RATE_LIMIT_ACCESS_POST_HOURLY`: default `20/hour`

### Environment profiles
- Local development: in-memory backend, relaxed limits optional.
- Staging: Redis backend, production-equivalent limits.
- Production: Redis backend, strict limits, alerting enabled.

## 7. Observability Requirements

Capture at minimum:
- Count of 429 responses by endpoint.
- Top source IPs triggering throttles.
- Ratio of throttled requests to total requests.
- Error budget impact (availability and latency).

Recommended log fields:
- Timestamp, route, method, remote IP, limiter policy name, decision (allow/deny).

## 8. Test Specification

### Unit-level checks
- Limiter initializes when enabled.
- Limiter bypasses gracefully when disabled.
- Access POST policy is stricter than global policy.

### Integration checks
- 6 rapid POST requests to the access endpoint -> 6th returns 429.
- `Retry-After` appears when throttled.
- Valid access request under threshold remains successful.
- Different IPs do not share the same counter unexpectedly.

### Load/abuse checks
- Simulate burst from one IP and verify throttling stability.
- Simulate normal traffic from many IPs and verify minimal false positives.

## 9. Acceptance Criteria

Implementation is complete when all criteria pass:

1. Global and access-route limits are active in staging.
2. 429 response behavior is consistent and user-friendly.
3. Proxy trust and Redis-backed storage are verified in production-like deployment.
4. Metrics show throttled requests are visible and attributable.
5. Automated tests cover success and throttle scenarios.

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| Misconfigured proxy trust causes all users to appear from one IP | High | Validate forwarded header chain in staging before production |
| In-memory backend in production causes inconsistent limits | High | Enforce Redis backend via environment validation |
| Limits too strict for shared NAT users | Medium | Start conservative; tune with real traffic metrics |
| Limits too loose to stop abuse | Medium | Add post-rollout review and tighten thresholds |

## 11. Alternative Options (If not using Flask-Limiter)

### Option A: Reverse proxy rate limiting (Nginx/Envoy)
- Apply limits at edge before requests reach Flask.
- Pros: lower app overhead, language-agnostic, simple ops control.
- Cons: less app context (course/lesson granularity harder), config complexity.

### Option B: CDN/WAF-based controls (Cloudflare, AWS WAF)
- Enforce bot mitigation and request-rate rules globally.
- Pros: best for volumetric attacks, managed service, fast to deploy.
- Cons: cost, vendor coupling, reduced application-specific logic.

### Option C: Fail2ban style IP blocking from logs
- Ban IPs after repeated failed POST attempts observed in logs.
- Pros: simple add-on for self-hosted Linux deployments.
- Cons: reactive, coarse-grained, less effective for distributed attacks.

### Option D: Challenge-based gating (Captcha or proof-of-work) on repeated failures
- Trigger challenge after N failed submissions from same source.
- Pros: better human/bot separation.
- Cons: user friction, accessibility impact, extra integration work.

## 12. Recommendation

Implement the baseline application-layer strategy now (Flask-Limiter + Redis + proxy trust) and pair it with a simple edge limit at reverse proxy level for defense in depth. If abuse continues after rollout, add WAF managed rules as the next control layer.
