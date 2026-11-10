
from typing import Literal

from workflows.states import EmailState


DashboardGroup = Literal[
    "needs_attention",
    "important_updates",
    "low_priority",
    "cleanup",
]


def choose_dashboard_group(
    state: EmailState,
) -> DashboardGroup:

    result = state["priority_result"]
    action = state["action_result"]

    if action.requires_action or action.needs_review:
        return "needs_attention"

    if result.priority in ("critical", "high"):
        return "important_updates"

    if result.category == "promotion":
        return "cleanup"

    return "low_priority"


def supervisor_node(state: EmailState) -> dict:
    group = choose_dashboard_group(state)

    return {
        "dashboard_group": group
    }
