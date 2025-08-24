from copy import deepcopy
from pathlib import Path
from typing import cast

from .llm import LLM
from .schemas import IntakeInterviewState, IntakeInterviewTurn
from .utils import format_messages, load_markdown

_BASE_DIR = Path(__file__).resolve().parent

USER_PROMPT = """
# Intake Interview Session State

## Collected Fields (could still be updated)
{collected_fields}

## To Be Collected Fields (avoid creating duplicates)
{to_collect_fields}

## Session Progress (watch time, adjust pace)
{turn_stats_summary}

# Conversation History
{formatted_history}

# Last User query:
{user_query}
"""


class LattiaAgent:
    prompt_filename: str = "proactive_interview_agent.md"
    model_name: str = "gpt-4.1-2025-04-14"
    history_window: int = 10  # how many previous messages to keep in context

    def __init__(self):
        self.llm = LLM(self.model_name)
        self.system_prompt = load_markdown(_BASE_DIR / "prompts" / self.prompt_filename)

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

        history = history[-self.history_window * 2 :]
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    formatted_history=format_messages(history),
                    user_query=user_query,
                    collected_fields=state.collected_fields_str,
                    to_collect_fields=state.to_collect_fields_str,
                    turn_stats_summary=state.stats.summary,
                ),
            },
        ]
        print(self.system_prompt)
        print(
            USER_PROMPT.format(
                formatted_history=format_messages(history),
                user_query=user_query,
                collected_fields=state.collected_fields_str,
                to_collect_fields=state.to_collect_fields_str,
                turn_stats_summary=state.stats.summary,
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
