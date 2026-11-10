
from unittest.mock import patch
from uuid import uuid4

from schemas.priority import EmailPriority
from agents.action_agent import ActionResult
from agents.summary_agent import SummaryResult
from agents.conversation_action_resolver import ConversationAction
from workflows.inbox_workflow import analyze_inbox


run_id = uuid4().hex
thread_id = f"test-thread-{run_id}"

emails = [
    {
        "id": f"{run_id}-1",
        "thread_id": thread_id,
        "received_at_ms": 1000,
        "sender": "recruiter@example.com",
        "subject": "Interview",
        "body": "Please confirm your availability.",
        "has_list_unsubscribe": False,
    },
    {
        "id": f"{run_id}-2",
        "thread_id": thread_id,
        "received_at_ms": 2000,
        "sender": "recruiter@example.com",
        "subject": "Re: Interview",
        "body": "Your interview is confirmed.",
        "has_list_unsubscribe": False,
    },
]

priorities = "Prioritize interviews."


def fake_message_analysis(state):
    priority = EmailPriority(
        priority="high",
        urgency="none",
        category="career",
        action_type="none",
        suggested_action="",
        explicit_deadline=None,
        summary="Interview scheduling update.",
        reason="Career-related information.",
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
        headline="Interview scheduling",
        summary="Interview scheduling update.",
        action_hint=None,
        importance_reason="Career-related information.",
    )

    return {
        **state,
        "priority_result": priority,
        "action_result": action,
        "summary_result": summary,
        "dashboard_group": "important_updates",
    }


def fake_summary(messages):
    return "The interview was confirmed."


def fake_resolver(messages):
    return ConversationAction(
        status="completed",
        current_action=None,
        reason="The recruiter confirmed the interview.",
        evidence=["Your interview is confirmed."],
        needs_review=False,
    )


print("\n--- FIRST SCAN ---")

with (
    patch(
        "workflows.inbox_workflow.email_workflow.invoke",
        side_effect=fake_message_analysis,
    ) as message_mock,
    patch(
        "workflows.inbox_workflow.summarize_conversation",
        side_effect=fake_summary,
    ) as summary_mock,
    patch(
        "workflows.inbox_workflow.resolve_conversation_actions",
        side_effect=fake_resolver,
    ) as resolver_mock,
):
    first = analyze_inbox(emails, priorities)

    assert message_mock.call_count == 2
    assert summary_mock.call_count == 1
    assert resolver_mock.call_count == 1

print("First scan saved results to SQLite.")

print("\n--- SECOND SCAN ---")

with (
    patch(
        "workflows.inbox_workflow.email_workflow.invoke",
        side_effect=AssertionError("Message cache missed"),
    ),
    patch(
        "workflows.inbox_workflow.summarize_conversation",
        side_effect=AssertionError("Summary cache missed"),
    ),
    patch(
        "workflows.inbox_workflow.resolve_conversation_actions",
        side_effect=AssertionError("Resolver cache missed"),
    ),
):
    second = analyze_inbox(emails, priorities)

assert len(first) == 1
assert len(second) == 1
assert first[0].model_dump() == second[0].model_dump()

print("Second scan reused cached analyses.")
print("\nAll SQLite cache tests passed!")
