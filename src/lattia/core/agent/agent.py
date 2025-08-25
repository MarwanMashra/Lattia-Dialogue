from copy import deepcopy
from pathlib import Path
from typing import cast

from lattia.core.utils.formatting import (
    format_messages,
    load_markdown,
    pretty_format,
)
from lattia.core.vector_db.retriever import SemanticRetriever

from .llm import LLM
from .schemas import IntakeInterviewState, IntakeInterviewTurn

_BASE_DIR = Path(__file__).resolve().parent


class LattiaAgent:
    system_prompt_filename: str = "proactive_interview_agent.md"
    user_message_filename: str = "user_message.md"
    model_name: str = "gpt-4.1-2025-04-14"
    conversation_history_window: int = 10

    # Retrieval config
    retrieval_top_k: int = 5  # how many similar questions to retrieve
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
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": self.user_message.format(
                    formatted_history=format_messages(history),
                    user_query=user_query,
                    collected_fields=state.collected_fields_str,
                    to_collect_fields=state.to_collect_fields_str,
                    turn_stats_summary=state.stats.summary,
                    relevant_questions=self._retrieve_relevant_questions(
                        self._build_semantic_query(user_query, state)
                    ),
                ),
            },
        ]
        print(self.system_prompt)
        print(
            self.user_message.format(
                formatted_history=format_messages(history),
                user_query=user_query,
                collected_fields=state.collected_fields_str,
                to_collect_fields=state.to_collect_fields_str,
                turn_stats_summary=state.stats.summary,
                relevant_questions=self._retrieve_relevant_questions(
                    self._build_semantic_query(user_query, state)
                ),
            )
        )

        new_turn = cast(
            IntakeInterviewTurn,
            self.llm.send_with_structured_response(
                messages=messages, response_format=IntakeInterviewTurn, verbose=True
            ),
        )
        print("LLM response:", new_turn)

        state.update_from_turn(new_turn)
        return new_turn.followup, state

    def _retrieve_relevant_questions(self, query_text: str) -> str:
        if self.retriever:
            items = self.retriever.retrieve(
                query_text,
                top_k=self.retrieval_top_k,
                score_threshold=self.retrieval_score_threshold,
            )
            if items:
                return pretty_format(items)
        return "No relevant questions found."

    @staticmethod
    def _build_semantic_query(user_query: str, state: IntakeInterviewState) -> str:
        return user_query
