from typing import Any

from pydantic import BaseModel, Field

# ====== TODO: Replace these with your real logic ======


class LLMResponse(BaseModel):
    reply: str
    health_update: dict[str, Any] = Field(default_factory=dict)
    is_done: bool = False


def generate_opening_question(profile: dict[str, Any]) -> str:
    # You can switch on profile['name'] if you want custom intros
    return f"Hello {profile['name']}! I am your assistant. How are you feeling today?"


def generate_reply(
    profile: dict[str, Any],
    history: list[dict[str, str]],
    user_message: str,
    is_done: bool = False,
) -> LLMResponse:
    if is_done or user_message.strip().lower() == "done":
        is_done = True
        reply = "Thanks, your interview is completed. You can still update your data."
    else:
        is_done = False
        reply = "Thanks. Your interview is completed. You can still update your data."
    # You can also return a partial health update to deep-merge
    return LLMResponse(
        reply=reply,
        health_update={},
        is_done=is_done,
    )
