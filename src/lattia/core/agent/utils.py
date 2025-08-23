from pathlib import Path


def format_messages(
    messages: list[dict[str, str]],
    user_name: str = "User",
    agent_name: str = "You",
) -> str:
    formatted_messages = []
    for msg in messages:
        name = user_name if msg["role"] == "user" else agent_name
        formatted_messages.append(f"{name}: {msg['content'].strip()}")
    return "\n".join(formatted_messages)


def load_markdown(filename: Path) -> str:
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()
