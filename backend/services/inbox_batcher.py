
from collections import OrderedDict


def group_messages_by_thread(
    emails: list[dict],
) -> list[list[dict]]:
    """
    Group messages by Gmail thread ID.

    Preserve the original order and never split
    a conversation across batches.
    """

    threads = OrderedDict()

    for email in emails:
        thread_id = email["thread_id"]

        if thread_id not in threads:
            threads[thread_id] = []

        threads[thread_id].append(email)

    return list(threads.values())


def create_thread_batches(
    emails: list[dict],
    batch_size: int = 5,
) -> list[list[dict]]:
    """
    Create batches of complete Gmail threads.

    batch_size counts conversations, not
    individual messages.
    """

    if batch_size < 1:
        raise ValueError(
            "batch_size must be at least 1"
        )

    threads = group_messages_by_thread(emails)

    batches = []

    for start in range(0, len(threads), batch_size):
        selected_threads = threads[
            start:start + batch_size
        ]

        batch_messages = []

        for thread in selected_threads:
            batch_messages.extend(thread)

        batches.append(batch_messages)

    return batches
