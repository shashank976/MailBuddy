
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CleanupAction = Literal[
    "keep",
    "archive",
    "unsubscribe",
]


class CleanupRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CleanupAction

    reason: str = Field(
        min_length=1,
        max_length=400,
    )

    approval_required: bool = True

    unsubscribe_available: bool = False


PROTECTED_CATEGORIES = {
    "career",
    "academics",
    "personal",
    "financial",
    "security",
}


def recommend_cleanup(
    *,
    priority: str,
    category: str,
    action_status: str,
    requires_action: bool,
    needs_review: bool,
    has_list_unsubscribe: bool = False,
) -> CleanupRecommendation:
    """
    Recommend a mailbox cleanup action.

    This function only returns a recommendation.
    It NEVER modifies Gmail.
    """

    def keep(reason: str) -> CleanupRecommendation:
        return CleanupRecommendation(
            action="keep",
            reason=reason,
            approval_required=True,
            unsubscribe_available=has_list_unsubscribe,
        )

    # Safety check 1:
    # Never recommend cleanup when the current
    # action is unresolved or uncertain.
    if requires_action or action_status in {
        "pending",
        "uncertain",
    }:
        return keep(
            "This conversation may require attention."
        )

    # Safety check 2:
    # Don't recommend cleanup for conversations
    # that still need human review.
    if needs_review:
        return keep(
            "This conversation requires review "
            "before cleanup can be recommended."
        )

    # Safety check 3:
    # Protect important conversations regardless
    # of whether they need a response.
    if priority in {"critical", "high"}:
        return keep(
            "This is an important conversation "
            "and should not be suggested for cleanup."
        )

    # Safety check 4:
    # Protect categories containing potentially
    # consequential information.
    if category in PROTECTED_CATEGORIES:
        return keep(
            "This category is protected from "
            "automatic cleanup recommendations."
        )

    # Be conservative: only low-priority
    # promotions qualify for cleanup in the MVP.
    if priority != "low" or category != "promotion":
        return keep(
            "There is insufficient evidence to "
            "recommend cleaning up this conversation."
        )

    # Prefer a verified unsubscribe mechanism
    # when Gmail supplies a List-Unsubscribe header.
    if has_list_unsubscribe:
        return CleanupRecommendation(
            action="unsubscribe",
            reason=(
                "Low-priority promotional conversation "
                "with an unsubscribe mechanism."
            ),
            approval_required=True,
            unsubscribe_available=True,
        )

    # Otherwise recommend archiving, not deleting.
    return CleanupRecommendation(
        action="archive",
        reason=(
            "Low-priority promotional conversation "
            "with no outstanding action."
        ),
        approval_required=True,
        unsubscribe_available=False,
    )
