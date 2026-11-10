
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from agents.conversation_action_resolver import (
    ConversationAction,
)
from agents.cleanup_agent import CleanupRecommendation

PRIORITY_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class ConversationCard(BaseModel):
    thread_id: str
    message_ids: list[str]
    message_count: int

    subject: str
    senders: list[str]
    latest_received_at_ms: int

    priority: str
    category: str
    dashboard_group: str

    summary: str = Field(min_length=1, max_length=600)

    action_status: str
    requires_action: bool
    suggested_action: str | None
    action_reason: str

    needs_review: bool
    gmail_url: str
    cleanup: CleanupRecommendation | None = None


def group_conversations(
    analyzed_emails: list[dict[str, Any]]
) -> list[list[dict[str, Any]]]:

    threads = defaultdict(list)

    for email in analyzed_emails:
        thread_id = email.get("thread_id") or email["email_id"]
        threads[thread_id].append(email)

    conversations = []

    for messages in threads.values():
        messages.sort(key=lambda m: m["received_at_ms"])
        conversations.append(messages)

    conversations.sort(
        key=lambda group: group[-1]["received_at_ms"],
        reverse=True
    )

    return conversations


def build_conversation_card(
    messages: list[dict[str, Any]],
    combined_summary: str,
    resolved_action: ConversationAction,
) -> ConversationCard:

    if not messages:
        raise ValueError("Cannot build an empty conversation card")

    latest = messages[-1]

    highest = max(
        messages,
        key=lambda m: PRIORITY_RANK[
            m["priority_result"].priority
        ]
    )["priority_result"]

    needs_review = resolved_action.needs_review

    if resolved_action.requires_action or needs_review:
        dashboard_group = "needs_attention"

    elif highest.priority in ("critical", "high"):
        dashboard_group = "important_updates"

    elif all(
        m["priority_result"].category == "promotion"
        for m in messages
    ):
        dashboard_group = "cleanup"

    else:
        dashboard_group = "low_priority"

    thread_id = latest.get("thread_id") or latest["email_id"]

    return ConversationCard(
        thread_id=thread_id,
        message_ids=[m["email_id"] for m in messages],
        message_count=len(messages),
        subject=latest["subject"],
        senders=list(dict.fromkeys(
            m["sender"] for m in messages
        )),
        latest_received_at_ms=latest["received_at_ms"],

        priority=highest.priority,
        category=highest.category,
        dashboard_group=dashboard_group,

        summary=combined_summary,

        action_status=resolved_action.status,
        requires_action=resolved_action.requires_action,
        suggested_action=resolved_action.current_action,
        action_reason=resolved_action.reason,

        needs_review=needs_review,

        gmail_url=(
            "https://mail.google.com/mail/u/0/"
            f"#all/{thread_id}"
        ),
    )
