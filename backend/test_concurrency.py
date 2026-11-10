from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from schemas.priority import EmailPriority
from agents.action_agent import ActionResult
from agents.summary_agent import SummaryResult
from agents.conversation_action_resolver import ConversationAction
from workflows.inbox_workflow import analyze_inbox


run_id = uuid4().hex
barrier = Barrier(2, timeout=10)

emails = [
    {
        "id": f"{run_id}-{i}",
        "thread_id": f"thread-{run_id}-{i}",
        "received_at_ms": 1000 + i,
        "sender": "recruiter@example.com",
        "subject": f"Interview update {i}",
        "body": f"Interview update number {i}.",
        "has_list_unsubscribe": False,
    }
    for i in range(2)
]

priorities = "Concurrency test: prioritize career updates."


def fake_workflow(state):
    # Each worker must reach this point
    # before either is allowed to continue.
    barrier.wait()

    priority = EmailPriority(
        priority="high",
        urgency="none",
        category="career",
        action_type="none",
        suggested_action="",
        explicit_deadline=None,
        summary="Interview update.",
        reason="Career-related email.",
        evidence=[],
        needs_review=False,
    )

    action = ActionResult(
        requires_action=False,
        action_type="none",
        description=None,
        deadline=None,
        needs_review=False,
    )

    summary = SummaryResult(
        headline="Interview update",
        summary="Interview update.",
        action_hint=None,
        importance_reason="Career-related email.",
    )

    return {
        **state,
        "priority_result": priority,
        "action_result": action,
        "summary_result": summary,
        "dashboard_group": "important_updates",
    }


def fake_summary(messages):
    return "An interview-related update."


def fake_resolver(messages):
    return ConversationAction(
        status="none",
        current_action=None,
        reason="No outstanding action.",
        evidence=[],
        needs_review=False,
    )


print("\n--- CONCURRENT FIRST SCAN ---")

with (
    patch(
        "workflows.inbox_workflow.email_workflow.invoke",
        side_effect=fake_workflow,
    ) as workflow_mock,
    patch(
        "workflows.inbox_workflow.summarize_conversation",
        side_effect=fake_summary,
    ),
    patch(
        "workflows.inbox_workflow.resolve_conversation_actions",
        side_effect=fake_resolver,
    ),
):
    first = analyze_inbox(
        emails,
        priorities,
        max_workers=2,
    )

    assert workflow_mock.call_count == 2

assert len(first) == 2

print("Both worker threads executed concurrently.")

print("\n--- CACHED SECOND SCAN ---")

with patch(
    "workflows.inbox_workflow.email_workflow.invoke",
    side_effect=AssertionError("Unexpected inference call"),
):
    second = analyze_inbox(
        emails,
        priorities,
        max_workers=2,
    )

assert len(second) == 2
assert [card.model_dump() for card in first] == [
    card.model_dump() for card in second
]

print("Second scan reused SQLite results.")
print("\nAll concurrency tests passed!")
