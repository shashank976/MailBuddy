
from gmail_service import get_recent_threads


def main():
    threads = get_recent_threads(
        hours=24,
        max_threads=5,
    )

    print("\n========== GMAIL THREAD TEST ==========\n")

    print("Threads found:", len(threads))

    total_messages = 0
    sent_messages = 0

    for index, thread in enumerate(threads, start=1):
        messages = thread["messages"]

        total_messages += len(messages)

        sent_count = sum(
            1 for message in messages
            if message["is_sent"]
        )

        sent_messages += sent_count

        print(f"\n--- Thread {index} ---")
        print("Message count:", len(messages))
        print("Sent replies:", sent_count)
        print(
            "Oldest message timestamp:",
            messages[0]["received_at_ms"],
        )
        print(
            "Newest message timestamp:",
            messages[-1]["received_at_ms"],
        )

        assert all(
            message["thread_id"] == thread["thread_id"]
            for message in messages
        )

        assert messages == sorted(
            messages,
            key=lambda message: message["received_at_ms"],
        )

    print("\n========== RESULTS ==========")
    print("Total conversations:", len(threads))
    print("Total messages retrieved:", total_messages)
    print("Sent messages found:", sent_messages)

    print("\nGmail thread retrieval test passed!")


if __name__ == "__main__":
    main()
