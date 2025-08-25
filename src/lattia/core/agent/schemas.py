from typing import Literal, get_args

from pydantic import BaseModel, Field

from lattia.core.utils.formatting import pretty_format

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
    "current_health_status",
]

ValueType = Literal[
    "single_choice",
    "multi_choice",
    "bucketed_choice",
    "yes_no",
    "scale_1_10",
    "free_text",
]

TO_COLLECT_TOKEN = "to_collect"  # default value before collection
DEFAULT_TURN_TARGET = 5  # default target turns per domain
MAX_TOTAL_TURN_TARGET = 30  # absolute max overall target turns
DEFAULT_TOTAL_TURN_TARGET = min(
    MAX_TOTAL_TURN_TARGET, int(len(get_args(intake_domain)) * DEFAULT_TURN_TARGET * 0.7)
)  # default overall target turns


# -----------------------------------------------------------------------#
# ----------------- LLM-facing Intake interview schemas ---------------- #
# -----------------------------------------------------------------------#
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
        description="Stable machine key in snake_case, unique across all intake domains and within the session.",
    )
    name: str = Field(
        ...,
        description="Human-readable name for the field, for use in UI and reports.",
    )
    description: str = Field(
        ...,
        description="A single-sentence statement (not a question) describing what the field represents, for use in UI and reports.",
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

    completeness_review: str = Field(
        ...,
        description=(
            "Concise reflection, 3 to 4 short sentences. First, decide whether to continue with the current domain or mark it "
            "as complete and move to another, based on factors such as: turns already spent in this domain, soft limits, "
            "whether the user’s latest answers show concerning signals or reassuring stability, lack of new signals, "
            "how many turns left for the interview, and how many other domains remain unexplored. Then add a one-sentence reflection on whether to "
            "consider the interview itself complete, based on soft turn limits and the number of domains already sufficiently covered or marked complete."
        ),
    )

    next_fields_thoughs: str = Field(
        ...,
        description=(
            "Concise reflection, from a functional-medicine physician perspective, on what additional information is important "
            "to collect next that has not yet been requested, and the plan to follow. Base this on the latest user response, "
            "prior context, clinical intuition, and general research knowledge. Target length 30 to 60 words."
        ),
    )
    field_requests_to_create: list[str] = Field(
        default_factory=list,
        description=(
            "List of keys for the IntakeFieldRequest items to create, Includes both: "
            "1. keys for the fields which values were collected in the `value_update_plan` but don't appear in the `Intake Session State` "
            "2. keys for the new fields based on the reasoning in next_fields_thoughs. "
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


class IntakeInterviewTurn(BaseModel):
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

    domains_to_mark_complete: list[intake_domain] = Field(
        default_factory=list,
        description="Domains to mark complete based on this turn's analysis. Empty list if anylsis concludes no domain is complete.",
    )

    mark_interview_complete: bool = Field(
        default=False,
        description="Set to true to mark the interview complete.",
    )

    new_fields_to_collect: list[IntakeFieldRequest] = Field(
        default_factory=list,
        description="Prioritized list of 0 to 2 IntakeFieldRequest items to collect next.",
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


# -----------------------------------------------------------------------#
# ------------------ Internal Intake interview schemas ----------------- #
# -----------------------------------------------------------------------#
class HealthDataEntry(BaseModel):
    """
    One collected piece of information from the interview.
    """

    key: str
    name: str
    description: str
    rationale: str
    value: str
    options: dict[str, str] | None = None


HealthData = dict[intake_domain, dict[str, HealthDataEntry]]


class IntakeField(IntakeFieldRequest):
    """
    An intake field being collected in the current intake session, along with its current value.
    """

    value: str

    @property
    def is_collected(self) -> bool:
        """Whether this field has been collected (i.e., has a value other than TO_COLLECT_TOKEN)."""
        return self.value != TO_COLLECT_TOKEN

    @classmethod
    def from_request(cls, req: IntakeFieldRequest) -> "IntakeField":
        return cls(**req.model_dump(), value=TO_COLLECT_TOKEN)


class IntakeTurnStats(BaseModel):
    """
    Tracks interview progress, overall and per domain.
    """

    class DomainTurnStat(BaseModel):
        turns: int = 0
        target: int = 6
        tolerance: int = 2
        completed: bool = False

        def increment(self) -> None:
            self.turns += 1

        def remaining(self) -> int:
            return max(self.target - self.turns, 0)

        def summary_row(self) -> str:
            tag = " [marked as completed]" if self.completed else ""
            return f"{self.turns} / {self.target} (+/- {self.tolerance}){tag}"

    # Overall counters
    total_turns: int = 0
    total_target: int = DEFAULT_TOTAL_TURN_TARGET  # adjust as you like

    domain_stats: dict[intake_domain, DomainTurnStat] = Field(
        default_factory=lambda: {
            d: IntakeTurnStats.DomainTurnStat() for d in get_args(intake_domain)
        }
    )

    def update(self, domain: intake_domain) -> None:
        """Increment overall turns and the counter for the given domain."""
        self.total_turns += 1
        self.domain_stats[domain].increment()

    def mark_completed(self, domain: intake_domain) -> None:
        """Mark a domain as completed."""
        self.domain_stats[domain].completed = True

    def total_turns_left(self) -> int:
        return max(self.total_target - self.total_turns, 0)

    @property
    def summary(self) -> str:
        """
        Return a human readable multi line summary, for example:

        - Total turns spent: 7
        - Total turns left: 13
        - Turns count per domain
          - sleep 3 / 10 (+/- 3)
          - nutrition 2 / 6 (+/- 2) [completed]
          - mental_health 2 / 6 (+/- 2)
        """
        lines = []
        lines.append(f"- Total turns spent: {self.total_turns}")
        lines.append(f"- Total turns left: {self.total_turns_left()}")
        lines.append("- Turns count per domain")
        for domain in get_args(intake_domain):
            stat = self.domain_stats[domain]
            lines.append(f"  - {domain} {stat.summary_row()}")
        return "\n".join(lines)


class IntakeInterviewState(BaseModel):
    """
    Container for all collected intake data during an interview.
    """

    fields: dict[str, IntakeField] = Field(default_factory=dict)
    stats: IntakeTurnStats = Field(default_factory=IntakeTurnStats, init=False)
    is_done: bool = False

    @property
    def collected_fields(self) -> dict[str, IntakeField]:
        """Fields that have been collected (i.e., have a value other than TO_COLLECT_TOKEN)."""
        return dict(filter(lambda item: item[1].is_collected, self.fields.items()))

    @property
    def to_collect_fields(self) -> dict[str, IntakeField]:
        """Fields that still need to be collected (i.e., have value TO_COLLECT_TOKEN)."""
        return dict(filter(lambda item: not item[1].is_collected, self.fields.items()))

    @staticmethod
    def fields_to_str(fields: dict[str, IntakeField]) -> str:
        """A formatted YAML-like string of the given fields."""
        return pretty_format({f.spec.key: f.model_dump() for f in fields.values()})

    def update_from_intake_field_request(self, req: IntakeFieldRequest) -> None:
        if req.spec.key not in self.fields:
            self.fields[req.spec.key] = IntakeField.from_request(req)
        else:
            print(
                f"WARNING: IntakeField key '{req.spec.key}' already exists in current state"
            )

    def update_from_intake_value_update(self, upd: IntakeValueUpdate) -> None:
        try:
            field = self.fields[upd.key]
            field.value = upd.value
        except KeyError:
            raise ValueError(
                f"WARNING: IntakeValueUpdate key '{upd.key}' not found in current state"
            )

    def update_from_turn(self, turn: IntakeInterviewTurn) -> None:
        for req in turn.new_fields_to_collect:
            self.update_from_intake_field_request(req)

        for upd in turn.value_updates:
            self.update_from_intake_value_update(upd)

        self.stats.update(turn.next_field_selection.domain)

        for domain in set(turn.domains_to_mark_complete):
            self.stats.mark_completed(domain)

        if turn.mark_interview_complete:
            self.is_done = True

    def to_health_data(self) -> HealthData:
        """Convert the collected fields into user-friendly HealthData format."""
        data: HealthData = {}
        for field in self.collected_fields:
            domain = field.spec.domain
            if domain not in data:
                data[domain] = {}
            data[domain][field.spec.key] = HealthDataEntry(
                key=field.spec.key,
                name=field.spec.name,
                description=field.spec.description,
                rationale=field.rationale,
                value=field.value,
                options=field.spec.options,
            )
        return data
