
import hashlib
import json
import os
import sqlite3

from pathlib import Path

from schemas.priority import EmailPriority
from agents.action_agent import ActionResult
from agents.summary_agent import (
    SummaryResult,
    ConversationSummary,
)
from agents.conversation_action_resolver import ConversationAction


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "mailbuddy.db"

# Increment these whenever analysis behavior changes.
MESSAGE_VERSION = "message-v1"
CONVERSATION_VERSION = "conversation-v1"


def fingerprint(data: dict) -> str:
    """Create a stable SHA-256 hash from input data."""

    serialized = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def get_connection():
    """Open a short-lived SQLite connection."""

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def initialize_database():
    """Create local cache tables and indexes."""

    with get_connection() as connection:
        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS message_cache (
                cache_key TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS conversation_cache (
                cache_key TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                action_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_id
            ON message_cache(message_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_thread_id
            ON conversation_cache(thread_id)
        """)

    os.chmod(DB_PATH, 0o600)


def message_cache_key(
    email: dict,
    user_priorities: str,
) -> str:
    """
    Include content and user priorities so a
    change in either invalidates the cache.
    """

    return fingerprint({
        "version": MESSAGE_VERSION,
        "model": os.getenv("OLLAMA_MODEL", "qwen3:4b"),
        "message": {
            "id": email["id"],
            "thread_id": email["thread_id"],
            "sender": email["sender"],
            "subject": email["subject"],
            "body": email["body"],
        },
        "user_priorities": user_priorities,
    })


def conversation_cache_key(
    messages: list[dict],
    user_priorities: str,
) -> str:
    """
    Include each message's analysis and position
    in the conversation timeline.
    """

    timeline = []

    for message in messages:
        timeline.append({
            "id": message["email_id"],
            "time": message["received_at_ms"],
            "sender": message["sender"],
            "subject": message["subject"],
            "body": message["body"],
            "priority": (
                message["priority_result"].model_dump(
                    exclude={"requires_action"}
                )
            ),
            "action": (
                message["action_result"].model_dump()
            ),
            "summary": (
                message["summary_result"].model_dump()
            ),
        })

    return fingerprint({
        "version": CONVERSATION_VERSION,
        "model": os.getenv("OLLAMA_MODEL", "qwen3:4b"),
        "user_priorities": user_priorities,
        "timeline": timeline,
    })


def load_message_analysis(key: str):
    """Return cached Pydantic objects or None."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT result_json
            FROM message_cache
            WHERE cache_key = ?
            """,
            (key,),
        ).fetchone()

    if row is None:
        return None

    try:
        data = json.loads(row["result_json"])

        return {
            "priority_result": EmailPriority.model_validate(
                data["priority_result"]
            ),
            "action_result": ActionResult.model_validate(
                data["action_result"]
            ),
            "summary_result": SummaryResult.model_validate(
                data["summary_result"]
            ),
            "dashboard_group": data["dashboard_group"],
        }

    except (ValueError, KeyError, TypeError):
        return None


def save_message_analysis(
    key: str,
    message_id: str,
    result: dict,
):
    """Persist validated message analysis."""

    payload = {
        "priority_result": (
            result["priority_result"].model_dump(
                exclude={"requires_action"}
            )
        ),
        "action_result": (
            result["action_result"].model_dump()
        ),
        "summary_result": (
            result["summary_result"].model_dump()
        ),
        "dashboard_group": result["dashboard_group"],
    }

    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO message_cache
            (cache_key, message_id, result_json)
            VALUES (?, ?, ?)
            """,
            (
                key,
                message_id,
                json.dumps(payload),
            ),
        )


def load_conversation_analysis(key: str):
    """Return (summary, action) or None."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT summary_json, action_json
            FROM conversation_cache
            WHERE cache_key = ?
            """,
            (key,),
        ).fetchone()

    if row is None:
        return None

    try:
        summary = ConversationSummary.model_validate_json(
            row["summary_json"]
        )

        action = ConversationAction.model_validate_json(
            row["action_json"]
        )

        return summary.summary, action

    except ValueError:
        return None


def save_conversation_analysis(
    key: str,
    thread_id: str,
    summary: str,
    action: ConversationAction,
):
    """Persist completed conversation analysis."""

    summary_model = ConversationSummary(
        summary=summary
    )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO conversation_cache
            (cache_key, thread_id, summary_json, action_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                key,
                thread_id,
                summary_model.model_dump_json(),
                action.model_dump_json(
                    exclude={"requires_action"}
                ),
            ),
        )
