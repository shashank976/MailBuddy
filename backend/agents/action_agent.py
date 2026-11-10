
from pydantic import BaseModel

from schemas.priority import EmailPriority


class ActionResult(BaseModel):
    requires_action: bool
    action_type: str
    description: str | None
    deadline: str | None
    needs_review: bool


def analyze_action(priority: EmailPriority) -> ActionResult:
    if not priority.requires_action:
        return ActionResult(
            requires_action=False,
            action_type="none",
            description=None,
            deadline=None,
            needs_review=priority.needs_review,
        )

    description = priority.suggested_action.strip()

    return ActionResult(
        requires_action=True,
        action_type=priority.action_type,
        description=description or None,
        deadline=priority.explicit_deadline,
        needs_review=priority.needs_review or not bool(description),
    )
