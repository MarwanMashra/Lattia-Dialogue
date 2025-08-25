import random
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lattia.core.utils.formatting import (
    camel_to_snake,
    format_messages,
    pretty_format,
    snake_to_human,
)
from lattia.core.vector_db.retriever import RelevantQuestion, SemanticRetriever

from .llm import LLM
from .schemas import (
    IntakeField,
    IntakeInterviewState,
    IntakeInterviewTurn,
    PostIntakeInterviewTurn,
)

_BASE_DIR = Path(__file__).resolve().parent


@dataclass
class Prompt:
    system_prompt: str
    user_message: str


OPENING_QUESTIONS = [
    "What’s one habit in your daily routine you think has the biggest impact on your health?",
    "How do you usually move your body during the week?",
    "When you think about your sleep, what feels most challenging right now?",
    "What’s been weighing on your mind the most these days?",
    "If you had to describe your eating style in a few words, how would you put it?",
    "Who in your life has the most influence on your health choices?",
    "Looking back, what past medical event has shaped how you view your health?",
    "How would you describe your relationship with things like alcohol or caffeine?",
    "What’s one personal routine you never skip, no matter what?",
]


class LattiaAgent:
    interview_system_prompt_filename: str = "interview_agent.md"
    interview_user_message_filename: str = "user_message.md"
    post_system_prompt_filename: str = "post_interview_agent.md"
    post_user_message_filename: str = "post_user_message.md"
    model_name: str = "gpt-4.1-2025-04-14"
    conversation_history_window: int = 10

    prompts_dir: Path = _BASE_DIR / "prompts"

    # Retrieval config
    retrieval_top_k_per_query: int = 3
    retrieval_score_threshold: float = 0.0

    def _load_prompt(self, filename: str) -> str:
        with open(self.prompts_dir / filename, "r", encoding="utf-8") as f:
            return f.read()

    def __init__(self, retriever: SemanticRetriever | None = None):
        self.retriever = retriever
        self.llm = LLM(self.model_name)
        self.interview_prompt = Prompt(
            system_prompt=self._load_prompt(self.interview_system_prompt_filename),
            user_message=self._load_prompt(self.interview_user_message_filename),
        )
        self.post_interview_prompt = Prompt(
            system_prompt=self._load_prompt(self.post_system_prompt_filename),
            user_message=self._load_prompt(self.post_user_message_filename),
        )

    def generate_opening_question(self, user_name) -> str:
        # TODO: figure out a smarter opening strategy :(
        intro = f"Hello {user_name}, I’m Lattia, your health intake interviewer. Let’s get started."
        return f"{intro} {random.choice(OPENING_QUESTIONS)}"

    def generate_reply(
        self,
        user_query: str,
        history: list[dict[str, str]],
        state: IntakeInterviewState,
        versbose: bool = False,
    ) -> tuple[str, IntakeInterviewState]:
        state = deepcopy(state)  # avoid mutating the input state

        user_message_placeholders = {
            "user_query": user_query,
            "formatted_history": format_messages(
                history[-self.conversation_history_window * 2 :]
            ),
            "collected_fields": IntakeInterviewState.fields_to_str(
                state.collected_fields
            ),
            "to_collect_fields": IntakeInterviewState.fields_to_str(
                state.to_collect_fields
            ),
            "turn_stats_summary": state.stats.summary,
            "relevant_questions": self._retrieve_relevant_questions(user_query, state),
        }

        if not state.is_done:
            prompt = self.interview_prompt
        else:
            prompt = self.post_interview_prompt

        user_message = prompt.user_message.format(**user_message_placeholders)
        messages = [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": user_message},
        ]
        if versbose:
            print(user_message)

        if not state.is_done:
            return self._handle_interview_turn(state, messages, versbose)

        return self._handle_post_interview_turn(state, messages, versbose)

    def _handle_interview_turn(
        self,
        state: IntakeInterviewState,
        messages: list[dict[str, str]],
        versbose: bool = False,
    ) -> tuple[str, IntakeInterviewState]:
        new_turn = cast(
            IntakeInterviewTurn,
            self.llm.send_with_structured_response(
                messages=messages, response_format=IntakeInterviewTurn, verbose=versbose
            ),
        )
        if versbose:
            print("LLM interview response:", new_turn)
            print()

        state.update_from_interview_turn(new_turn)
        return new_turn.followup, state

    def _handle_post_interview_turn(
        self,
        state: IntakeInterviewState,
        messages: list[dict[str, str]],
        versbose: bool = False,
    ) -> tuple[str, IntakeInterviewState]:
        post_turn = cast(
            PostIntakeInterviewTurn,
            self.llm.send_with_structured_response(
                messages=messages,
                response_format=PostIntakeInterviewTurn,
                verbose=versbose,
            ),
        )
        if versbose:
            print("LLM post-interview response:", post_turn)
            print()

        state.update_from_post_interview_turn(post_turn)
        return post_turn.followup, state

    @staticmethod
    def _format_retrieved_questions(items: list[RelevantQuestion]) -> str:
        questions = [
            {
                "key": camel_to_snake(it.key),
                "domain": it.domain_title,
                "example_question": it.label,
                "options": {camel_to_snake(k): v for k, v in it.options.items()},
            }
            for it in items
        ]
        return pretty_format(questions)

    def _retrieve_relevant_questions(
        self, user_query: str, state: IntakeInterviewState
    ) -> str:
        if self.retriever:
            queries = self._build_semantic_queries(user_query, state)
            results = self.retriever.retrieve_many(
                queries,
                top_k=self.retrieval_top_k_per_query,
                score_threshold=self.retrieval_score_threshold,
            )
            flat_unique_items = list({q.id: q for sub in results for q in sub}.values())

            if flat_unique_items:
                return self._format_retrieved_questions(flat_unique_items)
        return "No relevant questions found."

    @staticmethod
    def _build_semantic_queries(
        user_query: str, state: IntakeInterviewState
    ) -> list[str]:
        def format_field(field: IntakeField) -> str:
            return (
                f"Anylsis on the field {field.spec.name} that belongs to the "
                f"category {snake_to_human(field.spec.domain)}: {field.rationale}"
            )

        queries = []
        last_collected_field = (
            list(state.collected_fields.values())[-1]
            if state.collected_fields
            else None
        )
        if last_collected_field:
            queries.append(format_field(last_collected_field))

        last_to_collect_field = (
            list(state.to_collect_fields.values())[-1]
            if state.to_collect_fields
            else None
        )
        if last_to_collect_field:
            queries.append(format_field(last_to_collect_field))

        if not queries:
            queries.append(user_query)

        return queries
