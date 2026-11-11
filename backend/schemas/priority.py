
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


PriorityLevel = Literal[
    "critical",
    "high",
    "medium",
    "low",
]

UrgencyLevel = Literal[
    "immediate",
    "soon",
    "none",
]

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


NO_ACTION_VALUES = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "no action",
    "not applicable",
    "nothing",
}


class EmailPriority(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=False,
    )

    priority: PriorityLevel

    urgency: UrgencyLevel

    category: EmailCategory

    action_type: ActionType

    suggested_action: str = Field(
        description=(
            "Specific action required by the email. "
            "For reply, describe what to communicate. "
            "For complete_task, describe what to complete. "
            "For review, describe what must be examined. "
            "For none, return an empty string. "
            "Never return 'none' or 'null' as an action."
        )
    )

    explicit_deadline: str | None = Field(
        ...,
        description=(
            "Verbatim explicit action deadline from "
            "the email. Do not confuse event dates "
            "with submission or response deadlines. "
            "Return null when no deadline exists."
        )
    )

    summary: str = Field(
        min_length=1,
        max_length=600,
        description=(
            "Factual summary in 1-2 short sentences."
        ),
    )

    reason: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "One concise sentence explaining priority."
        ),
    )

    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "One or two short, exact quotations "
            "from the subject or body that support "
            "the classification. Do not paraphrase."
        ),
    )

    needs_review: bool = Field(
        default=False,
        description=(
            "True when classification, action, "
            "or supporting evidence is uncertain."
        ),
    )

    # -----------------------------------
    # NORMALIZE DEADLINES
    # -----------------------------------

    @field_validator(
        "explicit_deadline",
        mode="before",
    )
    @classmethod
    def normalize_deadline(cls, value):

        if isinstance(value, str):
            cleaned = value.strip()

            if cleaned.lower() in NO_ACTION_VALUES:
                return None

            return cleaned

        return value

    # -----------------------------------
    # NORMALIZE ACTION TEXT
    # -----------------------------------

    @field_validator(
        "suggested_action",
        mode="before",
    )
    @classmethod
    def normalize_action_text(cls, value):

        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        raise ValueError(
            "suggested_action must be a string"
        )

    # -----------------------------------
    # NORMALIZE EVIDENCE
    # -----------------------------------

    @field_validator(
        "evidence",
        mode="after",
    )
    @classmethod
    def normalize_evidence(cls, evidence):

        cleaned = []

        for quote in evidence:

            quote = quote.strip()

            if not quote:
                continue

            if quote not in cleaned:
                cleaned.append(quote)

        return cleaned

    # -----------------------------------
    # DERIVED ACTION STATUS
    # -----------------------------------

    @computed_field
    @property
    def requires_action(self) -> bool:
        return self.action_type != "none"

    # -----------------------------------
    # LOGICAL VALIDATION
    # -----------------------------------

    
    @model_validator(mode="after")
    def validate_consistency(self):

        action_text = self.suggested_action.lower()

        # No action means no suggested action.
        if self.action_type == "none":
            self.suggested_action = ""

        # An actionable email must have a specific
        # instruction, or it needs human review.
        elif action_text in NO_ACTION_VALUES:
            self.suggested_action = ""
            self.needs_review = True

        # Missing evidence matters most when
        # the classification is consequential.
        # Routine informational/promotional emails
        # should not require review solely because
        # evidence is absent.
        if (
            not self.evidence
            and (
                self.priority in {"critical", "high"}
                or self.action_type != "none"
            )
        ):
            self.needs_review = True

        # Immediate urgency with no action
        # is potentially inconsistent.
        if (
            self.urgency == "immediate"
            and self.action_type == "none"
        ):
            self.needs_review = True

        return self

