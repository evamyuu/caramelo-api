"""Guardrails around every model call, enforced in code.

Input: whatever comes from outside (what the user typed or said, the text of a
web page, link findings) is cleaned, wrapped in data markers the prompts tell
the model never to obey (:func:`fence`), and screened for prompt injection
(:func:`looks_like_injection`). Callers skip the model, or tighten the secure
room, when injection is detected.

Output: every reply that reaches the user's screen or voice goes through
:func:`guard_output`. A reply that asks for a password, code or CPF, tells the
user to move money, carries a link outside gov.br or a phone number, or leaks
the instructions is replaced by a safe fallback written in code. Tone rules
(no pet names, no barking) and markdown removal also apply here.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.ai.tone import respectful

logger = logging.getLogger(__name__)
_I = re.IGNORECASE

MAX_INPUT_CHARS = 500
MAX_REPLY_CHARS = 420
FENCE_OPEN, FENCE_CLOSE = "<<<", ">>>"

_INJECTION = re.compile(
    r"(?:ignor|esque[cç]|desconsider|descart|apag)\w*\s+(?:\w+\s+){0,3}?(?:instru[cç]|regra|ordem|ordens|orienta[cç]|prompt)"
    r"|ignore\s+(?:all\s+|the\s+|any\s+|previous\s+|prior\s+)*(?:instructions|rules|prompts?)"
    r"|(?:system|developer)\s+(?:prompt|message|mode)|prompt\s+do\s+sistema|modo\s+desenvolvedor|jailbreak"
    r"|voc[eê]\s+(?:agora\s+)?(?:[eé]|ser[aá])\s+(?:um|uma|o|a)\s+(?!pessoa)"
    r"|a\s+partir\s+de\s+agora,?\s+voc[eê]|finja\s+(?:que|ser)|aja\s+como|act\s+as|pretend\s+to"
    r"|nova[s]?\s+instru[cç]"
    # A page talking straight to the assistant: "Caramelo, digite...", "assistente: clique...".
    r"|\b(?:caramelo|assistente|ia|ai|bot|agente)\s*[,:]\s*(?:digite|clique|toque|envie|informe|preencha|"
    r"transfira|pague|fa[cç]a|confirme|aceite|autorize|abra|baixe|instale)",
    _I,
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁠-⁤]")

_NEGATION = re.compile(r"\b(?:n[aã]o|nunca|jamais|ningu[eé]m|nenhum|nenhuma|evite|cuidado|desconfie)\b", _I)
_ASKS_SECRET = re.compile(
    r"\b(?:informe|informar|digite|digitar|passe|passar|envie|enviar|mande|mandar|diga|dizer|fale|falar|"
    r"compartilhe|confirme|confirmar|forne[cç]a|me\s+d[eê]|anote)\b[^.!?]{0,40}"
    r"\b(?:senha|c[oó]digo|cpf|token|cart[aã]o|cvv|chave\s+pix)",
    _I,
)
_MOVES_MONEY = re.compile(
    r"\b(?:fa[cç]a|fazer|mande|mandar|envie|enviar|transfira|transferir|deposite|depositar|pague|pagar)\b"
    r"[^.!?]{0,30}\b(?:pix|transfer[eê]ncia|dep[oó]sito|pagamento|boleto|dinheiro|valor)",
    _I,
)
_URL = re.compile(
    r"\bhttps?://\S+|\bwww\.\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|xyz|top|shop|info|io|app|link|site)(?:\.br)?\b",
    _I,
)
_TRUSTED_HOSTS = re.compile(r"(?:^|[./])gov\.br\b", _I)
_PHONE = re.compile(
    r"(?<![\d.,])(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}(?![\d,])|\b0[38]00[\s-]?\d{3}[\s-]?\d{4}\b"
)
_LEAK = re.compile(
    r"\b(?:prompt|instru[cç][oõ]es\s+(?:do\s+sistema|internas|que\s+recebi)|system\s+message|"
    r"modelo\s+de\s+linguagem|language\s+model|sou\s+uma\s+(?:ia|intelig[eê]ncia)|gemini|openai|anthropic)\b",
    _I,
)
_MARKDOWN = re.compile(r"[*_#`>]+|\[(.*?)\]\(.*?\)")


def clean_input(text: str, limit: int = MAX_INPUT_CHARS) -> str:
    """Normalise outside text: no control or invisible characters, no fake data markers, bounded length."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _CONTROL.sub("", text).replace(FENCE_OPEN, "").replace(FENCE_CLOSE, "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def looks_like_injection(text: str) -> bool:
    """True when outside text tries to give the model instructions."""
    return bool(_INJECTION.search(clean_input(text, limit=20_000)))


def fence(label: str, text: str, limit: int = MAX_INPUT_CHARS) -> str:
    """Wrap outside text in data markers. Prompts say content inside them is never an instruction."""
    return f"{FENCE_OPEN}{label}: {clean_input(text, limit)}{FENCE_CLOSE}"


@dataclass(frozen=True)
class GuardResult:
    text: str
    violations: list[str] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.violations


def check_output(text: str) -> list[str]:
    """Names of the rules a reply breaks (empty when it is safe to show and speak)."""
    violations = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        negated = bool(_NEGATION.search(sentence))
        if _ASKS_SECRET.search(sentence) and not negated:
            violations.append("asks_for_secret")
        if _MOVES_MONEY.search(sentence) and not negated:
            violations.append("moves_money")
    if any(not _TRUSTED_HOSTS.search(url) for url in _URL.findall(text)):
        violations.append("untrusted_link")
    if _PHONE.search(text):
        violations.append("phone_number")
    if _LEAK.search(text):
        violations.append("leaks_instructions")
    return sorted(set(violations))


def guard_output(text: str | None, fallback: str) -> GuardResult:
    """Return a reply that is safe to show and speak, or ``fallback`` (written in code) when it is not."""
    if not text or not text.strip():
        return GuardResult(fallback)
    cleaned = respectful(_MARKDOWN.sub(lambda m: m.group(1) or "", text))
    violations = check_output(cleaned)
    if violations:
        logger.warning("Model reply blocked by guardrails: %s", ", ".join(violations))  # content is never logged
        return GuardResult(fallback, violations)
    if len(cleaned) > MAX_REPLY_CHARS:  # long replies are cut at a sentence end, for the voice
        cut = cleaned[:MAX_REPLY_CHARS]
        cleaned = cut[: max(cut.rfind("."), cut.rfind("!"), cut.rfind("?")) + 1] or cut
    return GuardResult(cleaned)
