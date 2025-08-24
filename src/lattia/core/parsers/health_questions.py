from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParsedQuestion:
    key: str
    domain_key: str
    domain_title: str
    label: str
    options: dict[str, str]  # <- dict of original options
    metadata: dict[str, Any]  # everything else, JSON-serializable


def _is_section_header(k: str, v: Any) -> bool:
    # Section headers look like "_physicalActivity": "----- ... -----"
    return k.startswith("_") and isinstance(v, str)


def parse_health_questions(path: Path) -> list[ParsedQuestion]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    arch = data.get("architecture", {})
    questions = data.get("questions", {})

    # Map domain key -> title
    domain_title_map: dict[str, str] = {}
    for dk, meta in arch.items():
        title = meta.get("title") if isinstance(meta, dict) else None
        domain_title_map[dk] = str(title or dk)

    current_domain_key: str | None = None
    out: list[ParsedQuestion] = []

    # dicts preserve insertion order, so headers will set the current domain
    for k, v in questions.items():
        if _is_section_header(k, v):
            current_domain_key = k.lstrip("_")
            continue

        if not isinstance(v, dict):
            continue

        label = v.get("label")
        if not label:
            continue

        domain_key = current_domain_key or "inconnu"
        domain_title = domain_title_map.get(domain_key, domain_key)

        # Use the original options dict if present and a dict, else {}
        options: dict[str, str] = {}
        raw_opts = v.get("options")
        if isinstance(raw_opts, dict):
            # Ensure values are strings
            options = {str(ok): str(ov) for ok, ov in raw_opts.items()}

        # Keep raw metadata, excluding label and options, but include extra context
        meta: dict[str, Any] = {
            kk: vv for kk, vv in v.items() if kk not in ("label", "options")
        }
        meta["domain_key"] = domain_key
        meta["domain_title"] = domain_title
        meta["source_key"] = k

        out.append(
            ParsedQuestion(
                key=k,
                domain_key=domain_key,
                domain_title=domain_title,
                label=str(label),
                options=options,
                metadata=meta,
            )
        )

    return out
