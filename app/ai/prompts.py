"""Every prompt sent to a model lives here, so wording is reviewed in one place.

Prompts are in Brazilian Portuguese because the assistant speaks to the end user
in that language. Safety rules (never ask for or type a password) are repeated in
the prompt *and* enforced in code by the secure session; the prompt is not the guard.
"""

from __future__ import annotations

import json
from typing import Any

PERSONA = (
    "Você é o Caramelo, um vira-lata caramelo que protege e ajuda uma pessoa idosa no celular. "
    "Fale em português do Brasil, com frases curtas e simples, sem termos técnicos. "
    "Nunca peça senha nem código. Se não souber, diga que não sabe."
)

_MAX_PAGE_TEXT = 1500
_HISTORY_WINDOW = 6


def link_verdict_speech(verdict: str, findings: list[str]) -> str:
    """Ask for a two-sentence explanation of a link verdict already decided by rules."""
    return (
        f"Analisei um link numa sala isolada. Veredito: {verdict}. "
        f"Sinais: {findings or 'nenhum'}. "
        "Explique para a Maria em no máximo 2 frases curtas o que fazer."
    )


def next_browser_action(
    task: str, url: str, history: list[str], page_text: str, elements: list[dict[str, Any]]
) -> str:
    """Ask for the next co-browsing step as a strict JSON object."""
    return (
        f"Tarefa da Maria: {task}\nURL: {url}\n"
        f"Já fiz: {history[-_HISTORY_WINDOW:]}\nTexto da página (resumo): {page_text[:_MAX_PAGE_TEXT]}\n"
        f"Elementos clicáveis: {json.dumps(elements, ensure_ascii=False)}\n"
        'Responda SÓ um JSON: {"action":"click|type|finish","index":numero,"text":"se type",'
        '"speech":"o que você diz para a Maria, 1 frase simples","result":"se finish, a resposta '
        'para a Maria em linguagem simples"}. Nunca digite senha. Use finish quando tiver a resposta.'
    )
