
import os
from concurrent.futures import ThreadPoolExecutor
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

from services.cache_service import (
    initialize_database,
    message_cache_key,
    conversation_cache_key,
    load_message_analysis,
    save_message_analysis,
    load_conversation_analysis,
    save_conversation_analysis,
)


DEFAULT_WORKERS = 2


def cache_debug(message: str):
    if os.getenv("MAILBUDDY_CACHE_DEBUG") == "1":
        print(message, flush=True)


def choose_dashboard_group(card) -> str:
    """
    Decide where a conversation belongs.

    Review flags remain visible on the card but
    do not automatically make low-priority mail
    require attention.
    """

    priority = card.priority

    # Low-value emails are filtered from the
    # main inbox, even when their evidence
    # could not be verified.
    if priority == "low":
        return "cleanup"

    # Important conversations needing action.
    if card.requires_action:
        return "needs_attention"

    # Don't bury potentially important uncertain
    # messages in the informational section.
    if priority in {"critical", "high"} and card.needs_review:
        return "needs_attention"

    # Everything else is informational.
    return "important_updates"



def make_initial_state(
    email: dict,
    user_priorities: str,
) -> dict:
    """Build the state expected by LangGraph."""

    return {
        "email_id": email["id"],
        "thread_id": email["thread_id"],
        "received_at_ms": email["received_at_ms"],
        "sender": email["sender"],
        "subject": email["subject"],
        "body": email["body"],
        "user_priorities": user_priorities,
    }


def run_message_workflow(state: dict) -> dict:
    """
    Execute a single email analysis.

    This runs in a worker thread.
    It does not access SQLite.
    """

    return email_workflow.invoke(state)


def analyze_inbox(
    emails: list[dict[str, Any]],
    user_priorities: str,
    max_workers: int = DEFAULT_WORKERS,
) -> list[ConversationCard]:
    """
    Analyze inbox messages using:

    - SQLite caching
    - Bounded concurrent message inference
    - Sequential SQLite writes
    - Conversation-level action resolution

    Never modifies Gmail.
    """

    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    initialize_database()

    if not emails:
        return []

    # Avoid analyzing duplicate Gmail messages.
    unique_emails = []
    seen_ids = set()

    for email in emails:
        if email["id"] not in seen_ids:
            seen_ids.add(email["id"])
            unique_emails.append(email)

    original_by_id = {
        email["id"]: email
        for email in unique_emails
    }

    # Preserve original ordering even though
    # analyses may finish at different times.
    results_by_id = {}

    # Entries contain (email, key, initial_state).
    cache_misses = []

    # -----------------------------------------
    # STEP 1: CHECK MESSAGE CACHE
    # -----------------------------------------

    for email in unique_emails:
        key = message_cache_key(
            email=email,
            user_priorities=user_priorities,
        )

        initial_state = make_initial_state(
            email,
            user_priorities,
        )

        cached = load_message_analysis(key)

        if cached is not None:
            cache_debug(
                f"[MESSAGE HIT] {email['id']}"
            )

            results_by_id[email["id"]] = {
                **initial_state,
                **cached,
            }

        else:
            cache_debug(
                f"[MESSAGE MISS] {email['id']}"
            )

            cache_misses.append(
                (email, key, initial_state)
            )

    # -----------------------------------------
    # STEP 2: ANALYZE ONLY CACHE MISSES
    # -----------------------------------------

    if cache_misses:
        worker_count = min(
            max_workers,
            len(cache_misses),
        )

        cache_debug(
            f"[WORKERS] Running {worker_count} worker(s)"
        )

        states = [
            state
            for _, _, state in cache_misses
        ]

        # executor.map preserves the order of states.
        # Only the inference happens in worker threads.
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="mailbuddy",
        ) as executor:

            analyzed_results = executor.map(
                run_message_workflow,
                states,
            )

            for (
                email,
                key,
                _,
            ), result in zip(
                cache_misses,
                analyzed_results,
            ):
                # Avoid caching incomplete results.
                if result.get("error"):
                    raise RuntimeError(
                        "Message analysis returned an error "
                        "and was not cached."
                    )

                # These may raise if inference returned
                # incomplete or malformed results.
                for required_field in (
                    "priority_result",
                    "action_result",
                    "summary_result",
                    "dashboard_group",
                ):
                    if result.get(required_field) is None:
                        raise RuntimeError(
                            "Incomplete message analysis: "
                            f"{required_field}"
                        )

                save_message_analysis(
                    key=key,
                    message_id=email["id"],
                    result=result,
                )

                results_by_id[email["id"]] = result

    # Reconstruct original message order.
    analyzed_emails = [
        results_by_id[email["id"]]
        for email in unique_emails
    ]

    # -----------------------------------------
    # STEP 3: GROUP MESSAGES BY CONVERSATION
    # -----------------------------------------

    conversations = group_conversations(
        analyzed_emails
    )

    cards = []

    # -----------------------------------------
    # STEP 4: CONVERSATION CACHE
    # -----------------------------------------

    for conversation in conversations:
        thread_id = conversation[-1]["thread_id"]

        key = conversation_cache_key(
            messages=conversation,
            user_priorities=user_priorities,
        )

        cached = load_conversation_analysis(key)

        summary_failed = False
        action_failed = False

        if cached is not None:
            cache_debug(
                f"[CONVERSATION HIT] {thread_id}"
            )

            combined_summary, resolved_action = cached

        else:
            cache_debug(
                f"[CONVERSATION MISS] {thread_id}"
            )

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
                        "Unable to resolve outstanding "
                        "conversation actions."
                    ),
                    evidence=[],
                    needs_review=True,
                )

                action_failed = True

            # Failures should be retried on the next scan.
            if not summary_failed and not action_failed:
                save_conversation_analysis(
                    key=key,
                    thread_id=thread_id,
                    summary=combined_summary,
                    action=resolved_action,
                )

        # -----------------------------------------
        # STEP 5: BUILD DASHBOARD CARD
        # -----------------------------------------

        card = build_conversation_card(
            messages=conversation,
            combined_summary=combined_summary,
            resolved_action=resolved_action,
        )

        if summary_failed or action_failed:
            card.needs_review = True
        # -----------------------------------------
        # STEP 6: SAFE CLEANUP RECOMMENDATIONS
        # -----------------------------------------

        has_list_unsubscribe = any(
            original_by_id[
                message["email_id"]
            ].get("has_list_unsubscribe", False)
            for message in conversation
        )

        recommendation = recommend_cleanup(
            priority=card.priority,
            category=card.category,
            action_status=card.action_status,
            requires_action=card.requires_action,
            needs_review=card.needs_review,
            has_list_unsubscribe=has_list_unsubscribe,
        )

        card.cleanup = recommendation

        # Keep cleanup suggestions, but determine
        # dashboard placement independently.
        card.dashboard_group = choose_dashboard_group(card)
        cards.append(card)

    return cards
