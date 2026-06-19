"""Session-based unlock state management."""

from flask import session


def grant_unlock(course_slug: str, lesson_id: int) -> None:
    """Record a lesson as unlocked in the current session."""
    unlocked = session.get("unlocked", {})
    if course_slug not in unlocked:
        unlocked[course_slug] = []
    
    # Store as a list of lesson IDs for serialization compatibility
    if lesson_id not in unlocked[course_slug]:
        unlocked[course_slug].append(lesson_id)
        # Re-assign to flag session as modified
        session["unlocked"] = unlocked


def grant_skeleton_unlock(course_slug: str, lesson_ids: list[int]) -> None:
    """Unlock all lessons in a course (skeleton key grant)."""
    unlocked = session.get("unlocked", {})
    unlocked[course_slug] = list(lesson_ids)
    session["unlocked"] = unlocked


def is_unlocked(course_slug: str, lesson_id: int) -> bool:
    """Check whether the current session has unlocked a specific lesson."""
    unlocked = session.get("unlocked", {})
    unlocked_lessons = unlocked.get(course_slug, [])
    return lesson_id in unlocked_lessons


def get_unlocked_lessons(course_slug: str) -> set[int]:
    """Return the set of unlocked lesson IDs for a course."""
    unlocked = session.get("unlocked", {})
    return set(unlocked.get(course_slug, []))
