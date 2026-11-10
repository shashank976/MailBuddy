
from typing import Any

from workflows.email_workflow import email_workflow

from agents.summary_agent import summarize_conversation

from services.conversation_service import (
    ConversationCard,
    group_conversations,
    build_conversation_card,
)


def analyze_inbox(
    emails: list[dict[str, Any]],
    user_priorities: str
) -> list[ConversationCard]:
    """
    Analyze individual messages, group Gmail threads,
    and create one dashboard card per conversation.
    """

    analyzed_emails = []

    for email in emails:
        initial_state = {
            "email_id": email["id"],
            "thread_id": email["thread_id"],
            "received_at_ms": email["received_at_ms"],
            "sender": email["sender"],
            "subject": email["subject"],
            "body": email["body"],
            "user_priorities": user_priorities,
        }

        result = email_workflow.invoke(initial_state)
        analyzed_emails.append(result)

    grouped_conversations = group_conversations(
        analyzed_emails
    )

    cards = []

    for conversation in grouped_conversations:

        try:
            combined_summary = summarize_conversation(
                conversation
            )

        except Exception as error:
            # A failed combined summary shouldn't prevent
            # the conversation from appearing in the UI.
            print(
                "Conversation summarization failed:",
                type(error).__name__
            )

            combined_summary = (
                conversation[-1]["summary_result"].summary
            )

        card = build_conversation_card(
            messages=conversation,
            combined_summary=combined_summary
        )

        cards.append(card)

    return cards
