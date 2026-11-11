
from services.cache_service import get_connection


CACHE_TABLES = (
    "message_cache",
    "conversation_cache",
    "dashboard_state",
)


def reset_mailbuddy_data() -> None:
    """
    Clear local analysis caches and saved dashboard.

    Does not delete Gmail messages, OAuth tokens,
    credentials, or user preferences.
    """

    with get_connection() as connection:
        # Only operate on tables that actually exist.
        existing_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table'"
            )
        }

        for table in CACHE_TABLES:
            if table in existing_tables:
                connection.execute(
                    f"DELETE FROM {table}"
                )
