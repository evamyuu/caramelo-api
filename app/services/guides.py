"""Guide mode: step-by-step help the user follows in their own browser.

Fallback for the secure room. Some sites refuse automated browsers on purpose:
gov.br rejects any captcha solved inside one (``ERL0000900``), however correct
the answer. Caramelo never disguises its browser to get past such protections.
Instead it opens the official site in the user's own browser, which passes those
checks, and speaks each step. The long-term path for gov.br is the official
Login Único integration for accredited partners.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# Page text that means "this site refused the automated browser".
_AUTOMATION_REJECTED = re.compile(r"captcha inv[aá]lido|ERL0000900", re.I)

# Hand-checked steps for the services Caramelo offers by name.
_CURATED_STEPS: dict[str, list[str]] = {
    "meu.inss.gov.br": [
        "Toque em “Entrar com gov.br”.",
        "Digite o seu CPF e toque em “Continuar”. Se aparecerem imagens, escolha as que o site pedir.",
        "Digite a sua senha do gov.br e toque em “Entrar”. Se pedir um código, ele chega no seu celular.",
        "Na tela do Meu INSS, toque na lupa e escreva “extrato de pagamento”.",
        "Toque em “Extrato de Pagamento”. O valor e a data do último pagamento aparecem no topo.",
    ],
}


@dataclass(frozen=True)
class Guide:
    url: str
    steps: list[str]


def automation_rejected(page_text: str) -> bool:
    """True when the page says the site refused the automated browser."""
    return bool(_AUTOMATION_REJECTED.search(page_text))


def guide_for(url: str, task: str) -> Guide:
    """Steps to do ``task`` on ``url`` in the user's own browser."""
    host = urlparse(url).hostname or ""
    steps = _CURATED_STEPS.get(host) or [
        "Abra o site no seu navegador.",
        "Se o site pedir, entre com a sua conta. CPF, senha e códigos, só você digita.",
        f"Procure por: {task}",
        "Se ficar em dúvida em alguma tela, me chame que eu te ajudo.",
    ]
    return Guide(url=url, steps=steps)
