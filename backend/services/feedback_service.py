
from datetime import datetime, timezone

from services.cache_service import get_connection


PRIORITIES = {
    "critical",
    "high",
    "medium",
    "low",
}

CATEGORIES = {
    "career",
    "academics",
    "personal",
    "financial",
    "security",
    "news",
    "promotion",
    "social",
    "other",
}


# -----------------------------------
# DATABASE INITIALIZATION
# -----------------------------------

def initialize_feedback():
    """Create the local feedback table if needed."""

    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                thread_id TEXT PRIMARY KEY,
                priority TEXT NOT NULL,
                category TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                remember_preference INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)


# -----------------------------------
# SAVE FEEDBACK
# -----------------------------------

def save_feedback(
    thread_id: str,
    priority: str,
    category: str,
    note: str = "",
    remember_preference: bool = False,
):
    """Save or update feedback for a conversation."""

    initialize_feedback()

    if priority not in PRIORITIES:
        raise ValueError("Invalid priority")

    if category not in CATEGORIES:
        raise ValueError("Invalid category")

    if remember_preference and not note.strip():
        raise ValueError(
            "Write a preference before choosing Remember."
        )

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as db:
        db.execute(
            """
            INSERT INTO user_feedback (
                thread_id,
                priority,
                category,
                note,
                remember_preference,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                priority = excluded.priority,
                category = excluded.category,
                note = excluded.note,
                remember_preference = excluded.remember_preference,
                updated_at = excluded.updated_at
            """,
            (
                thread_id,
                priority,
                category,
                note.strip(),
                int(remember_preference),
                updated_at,
            ),
        )

    return get_feedback(thread_id)


# -----------------------------------
# LOAD FEEDBACK
# -----------------------------------

def get_feedback(thread_id: str):
    """Get feedback for one conversation."""

    initialize_feedback()

    with get_connection() as db:
        row = db.execute(
            """
            SELECT *
            FROM user_feedback
            WHERE thread_id = ?
            """,
            (thread_id,),
        ).fetchone()

    return dict(row) if row else None


def get_all_feedback():
    """Get all saved conversation corrections."""

    initialize_feedback()

    with get_connection() as db:
        rows = db.execute(
            """
            SELECT *
            FROM user_feedback
            """
        ).fetchall()

    return {
        row["thread_id"]: dict(row)
        for row in rows
    }


# -----------------------------------
# LEARNED USER PREFERENCES
# -----------------------------------

def get_learned_preferences(limit: int = 5):
    """
    Get only preferences explicitly approved
    by the user for future classifications.
    """

    initialize_feedback()

    with get_connection() as db:
        rows = db.execute(
            """
            SELECT note
            FROM user_feedback
            WHERE remember_preference = 1
              AND TRIM(note) != ''
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [row["note"] for row in rows]


# -----------------------------------
# APPLY FEEDBACK TO DASHBOARD
# -----------------------------------


def apply_feedback(cards: list) -> list[dict]:
    """
    Apply saved user corrections to dashboard cards
    without changing original cached AI results.
    """

    feedback = get_all_feedback()
    results = []

    for card in cards:
        if hasattr(card, "model_dump"):
            updated = card.model_dump()
        else:
            updated = dict(card)

        correction = feedback.get(updated["thread_id"])

        if correction:
            updated["priority"] = correction["priority"]
            updated["category"] = correction["category"]
            updated["needs_review"] = False
            updated["user_corrected"] = True
        else:
            updated["user_corrected"] = False

        priority = updated["priority"]
        requires_action = bool(
            updated.get("requires_action")
        )
        needs_review = bool(
            updated.get("needs_review")
        )

        if priority == "low":
            updated["dashboard_group"] = "cleanup"

        elif requires_action:
            updated["dashboard_group"] = "needs_attention"

        elif (
            priority in {"critical", "high"}
            and needs_review
        ):
            updated["dashboard_group"] = "needs_attention"

        else:
            updated["dashboard_group"] = "important_updates"

        results.append(updated)

    return results
