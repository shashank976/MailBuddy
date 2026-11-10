
from services.inbox_loader import load_inbox_messages
from workflows.inbox_workflow import analyze_inbox
from services.cache_service import (
    message_cache_key,
    load_message_analysis,
)


USER_PRIORITIES = """
Prioritize software engineering internships,
recruiting emails, academic deadlines,
and important personal notifications.

Treat ordinary promotional emails as low priority.
"""


def main():
    print("Fetching Gmail messages...", flush=True)

    emails = load_inbox_messages(
        hours=24,
        max_threads=1,
    )

    print(f"Messages retrieved: {len(emails)}", flush=True)

    if not emails:
        print("No recent messages found.")
        return

    print("Running MailBuddy analysis...", flush=True)

    cards = analyze_inbox(
        emails=emails,
        user_priorities=USER_PRIORITIES,
    )

    print(f"\nConversation cards: {len(cards)}")

    for card in cards:
        print("\n--- RESULT ---")
        print("Message count:", card.message_count)
        print("Priority:", card.priority)
        print("Category:", card.category)
        print("Dashboard group:", card.dashboard_group)
        print("Action status:", card.action_status)
        print("Needs review:", card.needs_review)
        print(
            "Cleanup recommendation:",
            card.cleanup.action if card.cleanup else "None"
        )

    # -------------------------------------
    # AGENT DIAGNOSTICS
    # -------------------------------------

    print("\n--- AGENT DIAGNOSTICS ---")

    for email in emails:
        key = message_cache_key(
            email,
            USER_PRIORITIES,
        )

        cached = load_message_analysis(key)

        if cached is None:
            print("No cached analysis found.")
            continue

        priority = cached["priority_result"]
        action = cached["action_result"]

        print("Priority needs review:", priority.needs_review)
        print("Priority action type:", priority.action_type)
        print("Priority urgency:", priority.urgency)
        print("Action needs review:", action.needs_review)
        print("Action requires action:", action.requires_action)
        print("Evidence count:", len(priority.evidence))
        print(
            "Explicit deadline present:",
            bool(priority.explicit_deadline),
        )

    assert len(cards) == 1

    print("\nReal Gmail workflow test passed!")


if __name__ == "__main__":
    main()
