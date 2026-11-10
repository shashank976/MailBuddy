
from workflows.inbox_workflow import analyze_inbox


test_emails = [
    # Conversation 1: Already confirmed
    {
        "id": "email-001",
        "thread_id": "thread-confirmed",
        "received_at_ms": 1000,
        "sender": "recruiter@example.com",
        "subject": "Interview Scheduling",
        "body": (
            "Can you confirm whether Thursday "
            "works for your interview?"
        ),
    },
    {
        "id": "email-002",
        "thread_id": "thread-confirmed",
        "received_at_ms": 2000,
        "sender": "me@example.com",
        "subject": "Re: Interview Scheduling",
        "body": "Yes, Thursday works for me!",
    },
    {
        "id": "email-003",
        "thread_id": "thread-confirmed",
        "received_at_ms": 3000,
        "sender": "recruiter@example.com",
        "subject": "Re: Interview Scheduling",
        "body": (
            "Great, your interview is confirmed "
            "for Thursday. No further action is needed."
        ),
    },

    # Conversation 2: New action required
    {
        "id": "email-004",
        "thread_id": "thread-rescheduled",
        "received_at_ms": 4000,
        "sender": "recruiter2@example.com",
        "subject": "Interview Update",
        "body": (
            "Your interview was originally "
            "scheduled for Thursday."
        ),
    },
    {
        "id": "email-005",
        "thread_id": "thread-rescheduled",
        "received_at_ms": 5000,
        "sender": "recruiter2@example.com",
        "subject": "Re: Interview Update",
        "body": (
            "We need to move your interview to Friday. "
            "Please confirm your availability "
            "for the new date."
        ),
    },
]


cards = analyze_inbox(
    emails=test_emails,
    user_priorities=(
        "Prioritize software engineering "
        "interviews and recruiting emails."
    ),
)


for card in cards:
    print("\n--------------------")
    print(card.model_dump_json(indent=2))


assert len(cards) == 2

confirmed = next(
    c for c in cards
    if c.thread_id == "thread-confirmed"
)

rescheduled = next(
    c for c in cards
    if c.thread_id == "thread-rescheduled"
)

print("\n--- ACTION RESOLVER RESULTS ---")

print("Confirmed thread:", confirmed.action_status)
print("Rescheduled thread:", rescheduled.action_status)

assert confirmed.message_count == 3
assert rescheduled.message_count == 2

# These are the desired semantic outcomes.
assert confirmed.action_status == "completed", (
    "Confirmed conversation should have "
    "no outstanding scheduling action."
)

assert confirmed.requires_action is False

assert rescheduled.action_status == "pending", (
    "Rescheduled conversation should require "
    "confirmation of the new date."
)

assert rescheduled.requires_action is True

print("\nAll action resolver tests passed!")


assert confirmed.dashboard_group == "important_updates", (
    "A completed high-priority conversation should "
    "be categorized as Important Updates."
)

assert confirmed.needs_review is False

assert rescheduled.dashboard_group == "needs_attention"