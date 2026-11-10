
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field


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
    suggested_action: str | None

    needs_review: bool

    # Opens the full conversation in Gmail.
    gmail_url: str


def group_conversations(
    analyzed_emails: list[dict[str, Any]]
) -> list[list[dict[str, Any]]]:
    """Group analyzed messages by Gmail thread ID."""

    threads = defaultdict(list)

    for email in analyzed_emails:
        thread_id = email.get("thread_id") or email["email_id"]
        threads[thread_id].append(email)

    conversations = []

    for messages in threads.values():
        messages.sort(
            key=lambda message: message["received_at_ms"]
        )
        conversations.append(messages)

    conversations.sort(
        key=lambda group: group[-1]["received_at_ms"],
        reverse=True
    )

    return conversations


def build_conversation_card(
    messages: list[dict[str, Any]],
    combined_summary: str
) -> ConversationCard:
    """Create one dashboard card for a Gmail conversation."""

    if not messages:
        raise ValueError("Cannot build card from empty messages")

    latest = messages[-1]

    # Preserve the highest observed importance
    # rather than blindly taking the newest priority.
    highest_priority_message = max(
        messages,
        key=lambda message: PRIORITY_RANK[
            message["priority_result"].priority
        ]
    )

    highest_priority = highest_priority_message["priority_result"]

    # Keep the newest action information.
    # This is provisional: conversation-level action
    # resolution will be a separate feature.
    latest_action = latest["action_result"]

    if latest_action.requires_action:
        dashboard_group = "needs_attention"
    elif any(
        message["priority_result"].needs_review
        or message["action_result"].needs_review
        for message in messages
    ):
        dashboard_group = "needs_attention"
    elif highest_priority.priority in ("critical", "high"):
        dashboard_group = "important_updates"
    elif all(
        message["priority_result"].category == "promotion"
        for message in messages
    ):
        dashboard_group = "cleanup"
    else:
        dashboard_group = "low_priority"

    thread_id = latest.get("thread_id") or latest["email_id"]

    return ConversationCard(
        thread_id=thread_id,
        message_ids=[
            message["email_id"]
            for message in messages
        ],
        message_count=len(messages),
        subject=latest["subject"],
        senders=list(dict.fromkeys(
            message["sender"]
            for message in messages
        )),
        latest_received_at_ms=latest["received_at_ms"],
        priority=highest_priority.priority,
        category=highest_priority.category,
        dashboard_group=dashboard_group,
        summary=combined_summary,
        suggested_action=(
            latest_action.description
            if latest_action.requires_action
            else None
        ),
        needs_review=any(
            message["priority_result"].needs_review
            or message["action_result"].needs_review
            for message in messages
        ),
        gmail_url=(
            "https://mail.google.com/mail/u/0/"
            f"#all/{thread_id}"
        )
    )
