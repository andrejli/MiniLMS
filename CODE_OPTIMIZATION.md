# MiniLMS Code Optimization & Readability Roadmap

This document outlines proposed improvements for the MiniLMS Flask application to enhance performance, maintainability, and architectural clarity.

## 1. Performance Optimizations

### I/O Caching (High Impact)
*   **Current State:** `access.json` is re-read and parsed, and the `content/` directory is scanned on almost every request.
*   **Proposed Change:** Implement a caching layer or singleton Service class to load the course structure and access codes into memory on startup.
*   **Benefits:** Drastically reduces disk I/O and CPU overhead from JSON parsing.

### Markdown Pre-rendering (Medium Impact)
*   **Current State:** Markdown conversion to HTML happens on every lesson page load.
*   **Proposed Change:** Cache rendered HTML in memory. Use the lesson file's modification timestamp (`mtime`) as a cache-invalidation key.
*   **Benefits:** Faster response times for lesson pages.

### Optimized Data Structures (Low Impact)
*   **Current State:** Course lookups often involve iterating through lists.
*   **Proposed Change:** Maintain an in-memory dictionary of courses keyed by `slug` for O(1) lookups.

---

## 2. Readability & Architecture

### Flask Blueprints (High Impact)
*   **Current State:** Routes are registered via a manual dependency injection function in `app.py` with 10+ arguments.
*   **Proposed Change:** Modularize routes using [Flask Blueprints](https://flask.palletsprojects.com/en/stable/blueprints/).
*   **Benefits:** Follows Flask idioms, simplifies `app.py`, and makes the routing logic easier to navigate.

### Centralized Configuration (Medium Impact)
*   **Current State:** Environment variables and constants are scattered.
*   **Proposed Change:** Create a `config.py` file using class-based configuration (e.g., `DevelopmentConfig`, `ProductionConfig`).
*   **Benefits:** Provides a single source of truth for application settings.

### Service Layer Refactoring (Medium Impact)
*   **Current State:** `app.py` is cluttered with passthrough "compatibility wrappers."
*   **Proposed Change:** Directly use service modules or a registry object rather than manual wrappers in the main entry point.
*   **Benefits:** Reduces boilerplate and cognitive load when reading `app.py`.

### Type Hinting (Low Impact)
*   **Current State:** No type hints are utilized.
*   **Proposed Change:** Add PEP 484 type hints across the codebase.
*   **Benefits:** Improved IDE support, better self-documentation, and reduced risk of type-related bugs in nested data structures.

---

## 3. Security Enhancements

### Rate Limit Visibility
*   **Proposed Change:** Include standard rate-limit headers (e.g., `X-RateLimit-Limit`, `X-RateLimit-Remaining`) in all responses.
*   **Benefits:** Allows clients/scripts to gracefully handle throttling.

### Access Code Hashing
*   **Proposed Change:** Store access codes as salted hashes (e.g., Argon2 or Scrypt) instead of plain text in `access.json`.
*   **Benefits:** Protects access integrity even if the JSON file is compromised.
