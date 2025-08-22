from typing import Literal, get_args

from pydantic import BaseModel, Field

intake_domain = Literal[
    "basic_info",
    "lifestyle",
    "physical_activity",
    "sleep",
    "mental_health",
    "nutrition",
    "social_relations",
    "family_history",
    "medical_history",
    "substance_use",
    "personal_hygiene",
]

ValueType = Literal[
    "single_choice",
    "multi_choice",
    "bucketed_choice",
    "yes_no",
    "scale_1_10",
    "free_text",
]


class IntakeFieldSpec(BaseModel):
    """
    Specification of a single intake field to be collected during an intake session.

    Each field defines what kind of information should be gathered (e.g., smoking status, sleep duration,
    exercise habits), how it should be represented (value type), and how it fits into a broader intake domain
    (nutrition, sleep, lifestyle, etc.).

    The `value_type` controls how the field is answered. Whenever possible, prefer structured answer formats
    (`single_choice`, `multi_choice`, `bucketed_choice`, `yes_no`, `scale_1_10`) rather than open `free_text`.
    Structured formats ensure more consistent data collection, easier analysis, and better interoperability.

    In particular:
    - Use **single_choice** when exactly one option should be selected.
    - Use **multi_choice** when multiple options may apply.
    - Use **bucketed_choice** to capture numeric or continuous concepts in defined ranges, instead of free text.
      Examples: hours of sleep, frequency of gym visits, daily water intake, weekly alcohol consumption.
      Buckets should be meaningful, such as:
          - sleep_hours: ["<4h", "4–6h", "6–8h", ">8h"]
          - gym_frequency: ["never", "1–2x/week", "3–5x/week", "daily"]

    Reserve **free_text** only for cases where structured choices are impractical (e.g., "main personal goal" or
    "describe your main source of stress").

    Examples:

    - single_choice
      key: "exercise_duration"
      value_type: "single_choice"
      options: {"none":"None", "0to1h":"0–1 hour", "1to3h":"1–3 hours", "3to6h":"3–6 hours", "6plus":"6+ hours"}
      expected value: {"key":"exercise_duration","value":"1to3h"}

    - multi_choice
      key: "physical_activity_objectives"
      value_type: "multi_choice"
      options: {"improveHealth":"Improve health", "reduceStress":"Reduce stress", "buildStrength":"Build strength"}
      expected value: {"key":"physical_activity_objectives","value":["improveHealth","reduceStress"]}

    - bucketed_choice
      key: "sleep_hours"
      value_type: "bucketed_choice"
      options: {"lt4h":"<4h", "4to6h":"4–6h", "6to8h":"6–8h", "gt8h":">8h"}
      expected value: {"key":"sleep_hours","value":"6to8h"}

    - yes_no
      key: "is_smoker"
      value_type: "yes_no"
      expected value: {"key":"is_smoker","value":"no"}

    - scale_1_10
      key: "motivation_scale"
      value_type: "scale_1_10"
      expected value: {"key":"motivation_scale","value":"8"}

    - free_text
      key: "main_goal"
      value_type: "free_text"
      expected value: {"key":"main_goal","value":"Improve sleep quality"}
    """

    key: str = Field(
        ...,
        description="Stable machine key in snake_case, unique within the intake session.",
    )
    name: str = Field(
        ...,
        description="Human-readable name for the field, used in UI and reports.",
    )
    description: str = Field(
        ...,
        description="A one sentence description of the field, used in UI and reports.",
    )
    domain: intake_domain = Field(
        ...,
        description=f"The intake domain this field belongs to. Must be one of: {', '.join(get_args(intake_domain))}.",
    )
    value_type: ValueType = Field(
        ...,
        description="Controls how the value must be represented in IntakeValueUpdate.value",
    )
    options: dict[str, str] | None = Field(
        default=None,
        description="Choice map for single_choice, multi_choice or bucketed_choice. Keys are canonical codes to store, values are human labels.",
    )
    additional_value_format_specification: str | None = Field(
        default=None,
        description="Optional additional specification for the value format if needed, e.g., 'time_hhmm_24h' for time values in 24-hour format.",
    )


class IntakeFieldRequest(BaseModel):
    """
    Request to add exactly one intake field to the set of fields being collected in the current intake session.

    This is used to dynamically add fields that you consider relevant based on the conversation context, prior answers,
    values already collected, user concerns and goals, clinical heuristics, or physician intuition.

    Note: This can also be used to add a field for which the user has already provided a value without being prompted,
    e.g., if the user spontaneously mentions information relevant to one of the intake domains.
    """

    spec: IntakeFieldSpec
    rationale: str = Field(
        ...,
        description=(
            "Short justification linking this field to the user context or plan at this point in the interview, "
            "explaining why it is relevant to collect now. If the user has already provided the value spontaneously, "
            "set the rationale to 'User provided this information unprompted when asked about <context>'."
        ),
    )


class IntakeValueUpdate(BaseModel):
    """
    Add or update the normalized value for a single intake field in the current session.

    This is mainly used when the user provides information, either for a field that was
    previously created or for a new field just added via an IntakeFieldRequest.
    In practice, it works like an insert-or-update operation.

    - `key` must match an `IntakeFieldSpec.key` that was previously presented or another known field key.
    - `value` must be formatted according to the field's `value_type` and its `options` or
      `additional_value_format_specification`, if applicable.
    - Missing values: use one of the special tokens `"prefer_not_to_say"` or `"not_sure"` when the user refuses
      or cannot provide an answer. These tokens are the only valid non conforming values. Use them as the entire
      value for the field, do not mix them with other selections.
    """

    key: str
    domain: intake_domain = Field(
        ...,
        description=(
            f"The intake domain this field belongs to. Must be one of: {', '.join(get_args(intake_domain))}."
        ),
    )
    value: str = Field(
        ...,
        description=(
            "The field value, formatted according to its value_type and options (or "
            "additional_value_format_specification if applicable). "
            "For example: "
            "- For 'single_choice' or 'bucketed_choice', provide one of the option keys. "
            "- For 'multi_choice', provide a comma-separated list of option keys. "
            "- For 'scale_1_10', provide a number between 1 and 10. "
            "- For 'yes_no', provide 'yes' or 'no'. "
            "- For 'free_text', provide a text string."
        ),
    )


class TurnAnalysis(BaseModel):
    """
    Structured, turn-level reasoning that explains what the user just said, how it fits the context,
    which values can be updated now, and what new fields are likely useful to collect next.
    Keep each part very concise, use as few words as possible while staying clear.
    """

    response_interpretation: str = Field(
        ...,
        description=(
            "Interpret what the user just said. Summarize key signals and uncertainties from the latest answer. "
            "Target length 30 to 60 words."
        ),
    )

    context_link: str = Field(
        ...,
        description=(
            "Briefly connect the latest answer to the existing context, for example prior answers or known goals. "
            "Explain only what matters for this turn. Target length 20 to 40 words."
        ),
    )

    value_update_plan: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of field keys whose values can be added or updated now, based on the latest answer. "
            "List only keys, for example ['sleep_hours', 'is_smoker']. Rationale belongs in response_interpretation or context_link."
        ),
    )

    next_fields_thoughs: str = Field(
        ...,
        description=(
            "Concise reflection, from a functional-medicine physician perspective, on what additional information is important "
            "to collect next that has not yet been requested. Base this on the latest user response, prior context, "
            "clinical intuition, and general research knowledge. Target length 30 to 60 words."
        ),
    )


class NextFieldSelection(BaseModel):
    """
    Selection of the next intake field to ask.

    Contains both a short note explaining the reasoning behind the choice,
    and the key of the chosen field.
    """

    note: str = Field(
        ...,
        description=(
            "One to two sentences explaining why this field is the next best to ask. "
            "For example: immediate clinical relevance, dependency ordering, or user readiness."
        ),
    )
    key: str = Field(
        ...,
        description=(
            "Key of the next intake field to ask. Must be either: "
            "1) a key from new_fields_to_collect in this turn, or "
            "2) a previously requested field key that remains uncollected in the current intake session. "
            "Do not invent new keys here."
        ),
    )
    domain: intake_domain = Field(
        ...,
        description=("The intake domain this field belongs to."),
    )


class HealthIntakeTurn(BaseModel):
    """
    Single-turn decision payload for the intake flow.

    Provides a concise reasoning step for the current turn: interpreting what the user just said,
    recording any new or updated values, optionally proposing additional fields to collect,
    and outputting the follow-up question to continue the interview.
    """

    analysis: TurnAnalysis = Field(
        ...,
        description="Structured, turn-level reasoning that drives the rest of this payload.",
    )

    new_fields_to_collect: list[IntakeFieldRequest] = Field(
        default_factory=list,
        description=(
            "Prioritized list of 0 to 2 IntakeFieldRequest items to collect next. "
            "Prefer structured types over free_text, for example single_choice, multi_choice, or bucketed_choice. "
            "When proposing bucketed_choice, define meaningful ranges, for example sleep_hours: <4h, 4–6h, 6–8h, >8h. "
            "Each request must specify value_type and provide options when applicable."
        ),
    )

    value_updates: list[IntakeValueUpdate] = Field(
        default_factory=list,
        description=(
            "Normalized add or update values parsed from the last user response. "
            "Use the special tokens 'prefer_not_to_say', or 'not_sure' when appropriate."
        ),
    )

    next_field_selection: NextFieldSelection = Field(
        ...,
        description="The next intake field to ask, including both reasoning and key.",
    )

    followup: str = Field(
        ...,
        description=(
            "Exactly one clear question to continue the interview, covering a single topic. "
            "Align it with the immediate plan from the analysis and the highest-priority information need. "
            "When possible, present structured choices instead of open text."
        ),
    )


class HealthDataEntry(BaseModel):
    """
    One collected piece of information from the interview.
    """

    name: str
    description: str
    rationale: str
    value: str = "not_collected"
    options: dict[str, str] | None = None


class IntakeInterviewState(BaseModel):
    """
    Container for all collected intake data during an interview.
    """

    health_data: dict[intake_domain, dict[str, HealthDataEntry]] = Field(
        default_factory=lambda: {d: dict() for d in get_args(intake_domain)}
    )

    def update_from_intake_field_request(self, req: IntakeFieldRequest) -> None:
        """Create or refresh a HealthDataEntry from an IntakeFieldRequest."""
        try:
            spec = req.spec
            self.health_data[spec.domain][spec.key] = HealthDataEntry(
                name=spec.name,
                description=spec.description,
                rationale=req.rationale,
                options=spec.options,
            )
        except KeyError:
            print(
                f"Invalid domain '{req.spec.domain}' or key '{req.spec.key}' in IntakeFieldRequest"
            )

    def update_from_intake_value_update(self, upd: IntakeValueUpdate) -> None:
        """Update or create a HealthDataEntry with a new value based on an IntakeValueUpdate."""
        try:
            self.health_data[upd.domain][upd.key].value = upd.value
        except KeyError:
            print(
                f"Warning: Attempted to update non-existent field '{upd.key}' in domain '{upd.domain}'."
            )
