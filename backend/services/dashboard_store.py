
import json

from datetime import datetime, timezone

from services.cache_service import (
    get_connection,
    initialize_database,
)

from services.conversation_service import ConversationCard


def initialize_dashboard_store():
    """Create storage for the most recent completed scan."""

    initialize_database()

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_state (
                id INTEGER PRIMARY KEY
                    CHECK (id = 1),

                analyzed_at TEXT NOT NULL,
                cards_json TEXT NOT NULL
            )
        """)


def save_dashboard_cards(
    cards: list[ConversationCard],
) -> str:
    """
    Atomically replace the last successful scan.

    No raw email bodies are stored here.
    Cached summaries can still contain private data.
    """

    initialize_dashboard_store()

    analyzed_at = datetime.now(
        timezone.utc
    ).isoformat()

    cards_json = json.dumps([
        card.model_dump(mode="json")
        for card in cards
    ])

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO dashboard_state
                (id, analyzed_at, cards_json)
            VALUES (1, ?, ?)

            ON CONFLICT(id) DO UPDATE SET
                analyzed_at = excluded.analyzed_at,
                cards_json = excluded.cards_json
            """,
            (analyzed_at, cards_json),
        )

    return analyzed_at


def load_dashboard_cards() -> dict:
    """Read the last completed scan without Gmail or Ollama."""

    initialize_dashboard_store()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT analyzed_at, cards_json
            FROM dashboard_state
            WHERE id = 1
            """
        ).fetchone()

    if row is None:
        return {
            "last_analyzed_at": None,
            "cards": [],
        }

    cards = [
        ConversationCard.model_validate(item)
        for item in json.loads(row["cards_json"])
    ]

    return {
        "last_analyzed_at": row["analyzed_at"],
        "cards": cards,
    }
