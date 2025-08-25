import re
from typing import Any, Iterable


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


def pretty_format(
    data: Any,
    indent_size: int = 4,
    list_primitives_inline: bool = True,
    sort_keys: bool = False,
) -> str:
    """
    Return a human-readable YAML-like string for nested dicts and lists.

    Rules:
      - dict: 'key: value' for scalars, 'key:' then indented block for dicts or list-of-dicts.
      - list of primitives: inline like [a, b, c] if list_primitives_inline is True, otherwise block with '- item'.
      - list of dicts: expanded with '- ' on the same line as the first key.
    """
    sp = " " * indent_size

    def is_scalar(x: Any) -> bool:
        return isinstance(x, (str, int, float, bool)) or x is None

    def fmt_scalar(x: Any) -> str:
        # Keep it simple and readable
        if isinstance(x, str):
            return x
        if x is None:
            return "null"
        return str(x)

    def items_iter(d: dict[str, Any]) -> Iterable:
        return sorted(d.items(), key=lambda kv: kv[0]) if sort_keys else d.items()

    def render(obj: Any, indent: int) -> list[str]:
        if isinstance(obj, dict):
            lines: list[str] = []
            for k, v in items_iter(obj):
                pad = sp * indent
                if isinstance(v, dict):
                    lines.append(f"{pad}{k}:")
                    lines.extend(render(v, indent + 1))
                elif isinstance(v, list):
                    if not v:  # empty list
                        lines.append(f"{pad}{k}: []")
                    elif all(isinstance(it, dict) for it in v):
                        lines.append(f"{pad}{k}:")
                        lines.extend(render_list_of_dicts(v, indent))
                    elif list_primitives_inline:
                        inline = ", ".join(fmt_scalar(it) for it in v)
                        lines.append(f"{pad}{k}: [{inline}]")
                    else:
                        lines.append(f"{pad}{k}:")
                        for it in v:
                            lines.append(f"{pad}{sp}- {fmt_scalar(it)}")
                else:
                    lines.append(f"{pad}{k}: {fmt_scalar(v)}")
            return lines

        elif isinstance(obj, list):
            # Top-level list handling
            if not obj:
                return [sp * indent + "[]"]
            if all(isinstance(it, dict) for it in obj):
                return render_list_of_dicts(obj, indent)
            if list_primitives_inline:
                inline = ", ".join(fmt_scalar(it) for it in obj)
                return [sp * indent + f"[{inline}]"]
            return [sp * indent + f"- {fmt_scalar(it)}" for it in obj]

        else:
            return [sp * indent + fmt_scalar(obj)]

    def render_list_of_dicts(lst: list[dict[str, Any]], indent: int) -> list[str]:
        """Render list of dicts with '- ' starting the first key line."""
        lines: list[str] = []
        curr_pad = sp * indent
        child_pad = sp * (indent + 1)
        for d in lst:
            block = render(d, indent + 1)  # child block lines start with child_pad
            if not block:
                continue
            # Move first line up to the dash line
            first = block[0]
            # Remove the child padding from the first line only
            if first.startswith(child_pad):
                first_content = first[len(child_pad) :]
            else:
                first_content = first.lstrip()
            lines.append(f"{curr_pad}-   {first_content}")
            # Keep remaining lines as-is
            lines.extend(block[1:])
        return lines

    return "\n".join(render(data, 0))


def snake_to_camel(s: str) -> str:
    """Convert snake_case to camelCase."""
    parts = s.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def camel_to_snake(s: str) -> str:
    """Convert camelCase to snake_case."""
    return re.sub(r"([A-Z])", r"_\1", s).lower().lstrip("_")


def camel_to_human(s: str) -> str:
    """
    Convert camelCase or PascalCase to a human readable Title Case string.
    Examples:
      'exerciseDuration' -> 'Exercise Duration'
      'HTMLResponseCode' -> 'HTML Response Code'
    """
    if not s:
        return s
    # Insert space between lower/number and Upper, then between acronym and word start
    spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", s)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return spaced.strip().title()


def snake_to_human(s: str) -> str:
    """
    Convert snake_case to a human readable Title Case string.
    Example:
      'exercise_duration' -> 'Exercise Duration'
    """
    camel = snake_to_camel(s)
    return camel_to_human(camel)
