from typing import List, Dict, Any

# ====== TODO: Replace these with your real logic ======


def generate_opening_question(profile: Dict[str, Any]) -> str:
    # You can switch on profile['name'] if you want custom intros
    return f"Hello {profile['name']}! I am your assistant. How are you feeling today?"


def generate_reply(
    profile: Dict[str, Any],
    history: List[Dict[str, str]],
    user_message: str,
    is_done: bool,
) -> Dict[str, Any]:
    # Use is_done to pick one of your prompts later
    if not is_done:
        reply = "Thanks, noted. I still have a few questions for you."
    else:
        reply = "Thanks. Your interview is completed. You can still update your data."
    # You can also return a partial health update to deep-merge
    return {
        "reply": reply,
        "health_update": None,  # example: {"sleep": {"duration": {"value": "8 hours"}}}
    }
