from copy import deepcopy
from pathlib import Path
from typing import cast

from lattia.core.utils.formatting import (
    camel_to_snake,
    format_messages,
    load_markdown,
    pretty_format,
    snake_to_human,
)
from lattia.core.vector_db.retriever import RelevantQuestion, SemanticRetriever

from .llm import LLM
from .schemas import IntakeField, IntakeInterviewState, IntakeInterviewTurn

_BASE_DIR = Path(__file__).resolve().parent


class LattiaAgent:
    system_prompt_filename: str = "proactive_interview_agent.md"
    user_message_filename: str = "user_message.md"
    model_name: str = "gpt-4.1-2025-04-14"
    conversation_history_window: int = 10

    # Retrieval config
    retrieval_top_k_per_query: int = 3  # how many similar questions to retrieve
    retrieval_score_threshold: float = 0.0  # min similarity score to keep

    def __init__(self, retriever: SemanticRetriever | None = None):
        self.llm = LLM(self.model_name)
        self.system_prompt = load_markdown(
            _BASE_DIR / "prompts" / self.system_prompt_filename
        )
        self.user_message = load_markdown(
            _BASE_DIR / "prompts" / self.user_message_filename
        )
        self.retriever = retriever

    def generate_opening_question(self) -> str:
        # TODO: figure out an opening strategy
        return "Hello! I am your assistant. Can you tell me about your sleep habits?"

    def generate_reply(
        self,
        user_query: str,
        history: list[dict[str, str]],
        state: IntakeInterviewState,
    ) -> tuple[str, IntakeInterviewState]:
        state = deepcopy(state)  # avoid mutating the input state

        history = history[-self.conversation_history_window * 2 :]
        user_message_placeholders = {
            "formatted_history": format_messages(history),
            "user_query": user_query,
            "collected_fields": IntakeInterviewState.fields_to_str(
                state.collected_fields
            ),
            "to_collect_fields": IntakeInterviewState.fields_to_str(
                state.to_collect_fields
            ),
            "turn_stats_summary": state.stats.summary,
            "relevant_questions": self._retrieve_relevant_questions(user_query, state),
        }
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": self.user_message.format(**user_message_placeholders),
            },
        ]
        print(self.system_prompt)
        print(self.user_message.format(**user_message_placeholders))

        new_turn = cast(
            IntakeInterviewTurn,
            self.llm.send_with_structured_response(
                messages=messages, response_format=IntakeInterviewTurn, verbose=True
            ),
        )
        print("LLM response:", new_turn)

        state.update_from_turn(new_turn)
        return new_turn.followup, state

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
                f"The field {field.spec.name} belongs to the category {snake_to_human(field.spec.domain)}. "
                f"Analysis: {field.rationale}"
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
