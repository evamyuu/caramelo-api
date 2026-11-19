"""Respectful tone, enforced in code.

Older adults are adults: Caramelo calls the user by her name and never by pet
names or diminutives ("vovó", "querida", "dona"), and does not play the
cartoon dog ("au", "é só latir"). The persona prompt asks for this; this filter
guarantees it on every model reply before it reaches the screen or the voice.
"""

from __future__ import annotations

import re

USER_NAME = "Maria"

_I = re.IGNORECASE
_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # Pet names, alone or before the name: "vovó Maria", "Dona Maria", "vovozinha".
    (re.compile(
        r"\b(?:minha\s+)?(?:vov[óoô]zinha|vov[óoô]|v[óo]zinha|v[óo]|dona|querida|velhinha)\s+(?=Maria\b)", _I
    ), ""),
    (re.compile(r"\b(?:minha\s+)?(?:vov[óoô]zinha|vov[óoô]|v[óo]zinha|velhinha)\b", _I), USER_NAME),
    (re.compile(r",?\s*\b(?:minha\s+querida|querida|meu\s+bem|meu\s+anjo|benzinho|fofinha)\b", _I), ""),
    # The dog is a character in the design, not a voice that barks.
    # "au" counts as a bark only as a word of its own ("Au, ...", "Au au!"), never inside "Autorize".
    (re.compile(r"\bau(?:[\s,!.]+au)*(?:[\s,!.]+|$)(?![a-záéíóúâêôãõç])", _I), ""),
    (re.compile(r"é só latir", _I), "é só me chamar"),
]


def respectful(text: str) -> str:
    """Remove pet names, diminutives and barking from a model reply."""
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)  # space left before punctuation
    text = re.sub(r"([,!?.])\1+", r"\1", text)
    text = re.sub(r"(^|[.!?]\s+)([a-záéíóúâêôãõç])", lambda m: m.group(1) + m.group(2).upper(), text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()
