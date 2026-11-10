
from workflows.inbox_workflow import analyze_inbox


test_emails = [
    {
        "id": "email-001",
        "thread_id": "thread-interview",
        "received_at_ms": 1000,
        "sender": "recruiter@example.com",
        "subject": "Interview Invitation",
        "body": (
            "We'd like to schedule an interview "
            "for Thursday. Please confirm availability."
        )
    },
    {
        "id": "email-002",
        "thread_id": "thread-interview",
        "received_at_ms": 2000,
        "sender": "recruiter@example.com",
        "subject": "Re: Interview Invitation",
        "body": (
            "Your interview is confirmed for Thursday."
        )
    },
    {
        "id": "email-003",
        "thread_id": "thread-interview",
        "received_at_ms": 3000,
        "sender": "recruiter@example.com",
        "subject": "Re: Interview Invitation",
        "body": (
            "The interview has been moved to Friday "
            "instead of Thursday."
        )
    },
    {
        "id": "email-004",
        "thread_id": "thread-promotion",
        "received_at_ms": 4000,
        "sender": "offers@store.com",
        "subject": "Weekend Sale",
        "body": (
            "Get 50% off selected clothing "
            "this weekend."
        )
    }
]


cards = analyze_inbox(
    emails=test_emails,
    user_priorities=(
        "Prioritize software engineering internships, "
        "interview scheduling, and academic deadlines. "
        "Treat clothing promotions as low priority."
    )
)


print("\n========== CONVERSATION CARDS ==========\n")

for card in cards:
    print(card.model_dump_json(indent=2))
    print()


assert len(cards) == 2, (
    f"Expected 2 conversations, got {len(cards)}"
)

interview = next(
    card for card in cards
    if card.thread_id == "thread-interview"
)

promotion = next(
    card for card in cards
    if card.thread_id == "thread-promotion"
)

assert interview.message_count == 3
assert promotion.message_count == 1

assert interview.message_ids == [
    "email-001",
    "email-002",
    "email-003"
]

assert interview.priority in ("high", "critical")

assert promotion.priority == "low"

assert "Friday" in interview.summary, (
    "The combined summary should mention "
    "the new interview day."
)

print("All conversation tests passed!")
