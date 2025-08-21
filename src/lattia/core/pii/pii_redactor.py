import re
from functools import cache

from gliner import GLiNER

from .pii_type import PIIType


@cache
def get_redactor() -> "PIIRedactor":
    redactor = PIIRedactor()
    # warm up the model
    redactor.redact(
        "My name is John Doe and I was born on 1990-01-01, so I'm 30 years old. My phone number is 123-456-7890."
    )
    return redactor


class PIIRedactor:
    _model_name = "urchade/gliner_multi_pii-v1"
    _default_allowed_entities: list[PIIType] = [
        PIIType.PERSON,
        PIIType.MEDICATION,
        PIIType.MEDICAL_CONDITION,
        PIIType.USERNAME,
        PIIType.BLOOD_TYPE,
    ]

    def __init__(self):
        self.model = GLiNER.from_pretrained(self._model_name)

    def redact(self, text: str, allowed: list[PIIType] | None = None) -> str:
        allowed_set = (
            set(allowed) if allowed is not None else set(self._default_allowed_entities)
        )
        to_redact = set(PIIType) - allowed_set

        candidate_labels = [p.value for p in PIIType]
        entities = self.model.predict_entities(text, candidate_labels)

        value_to_enum = {p.value: p for p in PIIType}

        spans: list[tuple[int, int, str]] = []
        for ent in entities:
            label = ent.get("label")
            pii = value_to_enum.get(label)
            if pii is None or pii not in to_redact:
                continue

            mask = pii.mask  # e.g. "[PHONE NUMBER]"
            start = ent.get("start")
            end = ent.get("end")
            ent_text = ent.get("text", "")

            if (
                isinstance(start, int)
                and isinstance(end, int)
                and 0 <= start < end <= len(text)
            ):
                spans.append((start, end, mask))
            elif ent_text:
                # Fallback if offsets are missing
                for m in re.finditer(re.escape(ent_text), text):
                    spans.append((m.start(), m.end(), mask))

        if not spans:
            return text

        # 5) Resolve overlaps, prefer longer spans
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        merged: list[tuple[int, int, str]] = []
        for s in spans:
            if not merged or s[0] >= merged[-1][1]:
                merged.append(s)
            else:
                # overlapping, keep the longer one already placed
                prev = merged[-1]
                if (s[1] - s[0]) > (prev[1] - prev[0]):
                    merged[-1] = s

        # 6) Apply replacements right to left to keep indices stable
        cleaned_text = text
        for start, end, mask in sorted(merged, key=lambda s: s[0], reverse=True):
            cleaned_text = cleaned_text[:start] + mask + cleaned_text[end:]

        return cleaned_text
