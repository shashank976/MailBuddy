
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

PriorityLevel = Literal["critical", "high", "medium", "low"]

UrgencyLevel = Literal["immediate", "soon", "none"]

EmailCategory = Literal[
    "career",
    "academics",
    "personal",
    "financial",
    "security",
    "news",
    "promotion",
    "social",
    "other",
]

ActionType = Literal[
    "reply",
    "review",
    "complete_task",
    "none",
]


class EmailPriority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: PriorityLevel
    urgency: UrgencyLevel
    category: EmailCategory

    action_type: ActionType

    suggested_action: str = Field(
        description=(
            "Specific action the recipient should take. "
            "For reply, state what to respond about. "
            "For complete_task, name the actual task. "
            "For review, describe what needs reviewing. "
            "When action_type is none, return an empty string."
        )
    )

    explicit_deadline: str | None = Field(
        ...,
        description=(
            "Exact text of an explicit action deadline "
            "from the email, such as "
            "'November 12 at 11:59 PM'. "
            "Do not confuse an event date with a deadline. "
            "Return null if no action deadline is stated."
        )
    )

    summary: str = Field(
        min_length=1,
        max_length=600,
        description="Concise factual summary of the email."
    )

    reason: str = Field(
        min_length=1,
        max_length=400,
        description="Why this email received its priority."
    )

    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Short verbatim quotes supporting the classification. "
            "Each quote must appear in the email subject or body."
        )
    )

    needs_review: bool = False


    @field_validator(
        "explicit_deadline",
        mode="before"
    )
    
    @classmethod
    def normalize_deadline(cls, value):
        if isinstance(value, str):
            if value.strip().lower() in {
                "null",
                "none",
                "",
                "n/a"
            }:
                return None

        return value


    @computed_field
    @property
    def requires_action(self) -> bool:
        return self.action_type != "none"

    @model_validator(mode="after")
    def validate_action(self):

        self.suggested_action = self.suggested_action.strip()

        if self.action_type == "none":
            self.suggested_action = ""

        elif not self.suggested_action:
            self.needs_review = True

        return self
