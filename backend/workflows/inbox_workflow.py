
from typing import Any

from workflows.email_workflow import email_workflow

from agents.summary_agent import summarize_conversation

from agents.conversation_action_resolver import (
    ConversationAction,
    resolve_conversation_actions,
)

from agents.cleanup_agent import recommend_cleanup

from services.conversation_service import (
    ConversationCard,
    group_conversations,
    build_conversation_card,
)


def analyze_inbox(
    emails: list[dict[str, Any]],
    user_priorities: str,
) -> list[ConversationCard]:
    """
    Analyze individual messages, group conversations,
    resolve actions, and recommend safe cleanup.

    No Gmail modifications are performed.
    """

    analyzed_emails = []

    # Keep original Gmail metadata available
    # even after passing messages through LangGraph.
    original_by_id = {
        email["id"]: email
        for email in emails
    }

    # 1. Run each email through LangGraph.
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

    # 2. Group messages by Gmail thread ID.
    conversations = group_conversations(
        analyzed_emails
    )

    cards = []

    for conversation in conversations:

        # 3. Summarize the complete available timeline.
        summary_failed = False

        try:
            combined_summary = summarize_conversation(
                conversation
            )

        except Exception as error:
            print(
                "Conversation summary failed:",
                type(error).__name__,
            )

            combined_summary = (
                conversation[-1]["summary_result"].summary
            )

            summary_failed = True

        # 4. Resolve outstanding conversation actions.
        try:
            resolved_action = resolve_conversation_actions(
                conversation
            )

        except Exception as error:
            print(
                "Action resolution failed:",
                type(error).__name__,
            )

            resolved_action = ConversationAction(
                status="uncertain",
                current_action=None,
                reason=(
                    "Unable to determine outstanding "
                    "actions automatically."
                ),
                evidence=[],
                needs_review=True,
            )

        # 5. Build the conversation card.
        card = build_conversation_card(
            messages=conversation,
            combined_summary=combined_summary,
            resolved_action=resolved_action,
        )

        if summary_failed:
            card.needs_review = True
            card.dashboard_group = "needs_attention"

        # 6. Check whether any message in the
        # conversation has an unsubscribe header.
        has_list_unsubscribe = any(
            original_by_id[message["email_id"]].get(
                "has_list_unsubscribe",
                False
            )
            for message in conversation
        )

        # 7. Produce a cleanup recommendation.
        recommendation = recommend_cleanup(
            priority=card.priority,
            category=card.category,
            action_status=card.action_status,
            requires_action=card.requires_action,
            needs_review=card.needs_review,
            has_list_unsubscribe=has_list_unsubscribe,
        )

        card.cleanup = recommendation

        # 8. Route eligible cleanup recommendations
        # into the Cleanup section.
        if recommendation.action in {
            "archive",
            "unsubscribe",
        }:
            card.dashboard_group = "cleanup"

        elif card.dashboard_group == "cleanup":
            # A previously provisional cleanup grouping
            # did not pass the safety checks.
            card.dashboard_group = "low_priority"

        cards.append(card)

    return cards
