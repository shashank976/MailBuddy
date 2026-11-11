
from gmail_service import get_recent_threads


def load_inbox_messages(
    hours: int = 24,
    max_threads: int | None = None,
) -> list[dict]:
    """
    Fetch complete Gmail conversations.

    max_threads=None fetches all matching threads
    from the requested time window.

    Flatten the messages for MailBuddy's existing
    LangGraph workflow, avoiding duplicate IDs.
    """

    threads = get_recent_threads(
        hours=hours,
        max_threads=max_threads,
    )

    messages = []
    seen_ids = set()

    for thread in threads:
        for message in thread["messages"]:
            message_id = message["id"]

            if message_id in seen_ids:
                continue

            seen_ids.add(message_id)
            messages.append(message)

    return messages
