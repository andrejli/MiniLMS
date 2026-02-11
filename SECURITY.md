# Security notes

## Current access model
The app currently protects lessons with shared access codes and no login. This is acceptable for demos or low-stakes content, but it is not strong access control.

## Pros
- Very low friction for users
- Simple implementation and maintenance
- Fast to share and test

## Risks
- Codes can be forwarded to anyone
- No per-user revocation
- No rate limiting by default
- No audit trail of who accessed what
- A leaked code must be rotated everywhere

## Recommended minimum hardening
If this will be used for paid or restricted content, consider:
1. Single-use codes stored server-side with expiry
2. Rate limiting on code entry
3. Logging code usage (time/IP) for abuse detection
4. Optional email capture to bind a code to one person

## When this is OK
- Internal demos
- Early-stage prototypes
- Free or low-risk content
