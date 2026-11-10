
from gmail_service import get_recent_threads


def load_inbox_messages(
    hours: int = 24,
    max_threads: int = 5,
) -> list[dict]:
    """
    Fetch complete Gmail threads and flatten
    their messages for the existing workflow.
    """

    threads = get_recent_threads(
        hours=hours,
        max_threads=max_threads,
    )

    messages = []
    seen_ids = set()

    for thread in threads:
        for message in thread["messages"]:
            if message["id"] not in seen_ids:
                seen_ids.add(message["id"])
                messages.append(message)

    return messages
