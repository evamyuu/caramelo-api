"""Isolated link scanner ("sala isolada").

Opens a suspicious URL in a disposable browser *before* the user does and scores
it. The scanner only observes: it never logs in, types or submits anything.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.ai import client as llm
from app.ai import guardrails, prompts
from app.core.browser import launch
from app.services.risk import CAUTION_THRESHOLD, MAX_SCORE, SCAM_THRESHOLD

# Brands commonly impersonated in Brazil, mapped to their official domains.
OFFICIAL_DOMAINS: dict[str, tuple[str, ...]] = {
    "gov.br": ("gov.br",),
    "inss": ("gov.br",),
    "receita federal": ("gov.br",),
    "banco do brasil": ("bb.com.br",),
    "caixa": ("caixa.gov.br",),
    "itaú": ("itau.com.br",),
    "itau": ("itau.com.br",),
    "bradesco": ("bradesco.com.br",),
    "santander": ("santander.com.br",),
    "nubank": ("nubank.com.br",),
    "correios": ("correios.com.br",),
    "serasa": ("serasa.com.br",),
    "mercado pago": ("mercadopago.com.br",),
}
# Detection vocabularies are Portuguese because the scanned pages are.
URGENCY_TERMS = (
    "urgente", "bloquead", "suspens", "último aviso", "ultimo aviso", "imediatamente", "expira",
    "regularize", "cancelad", "multa", "prêmio", "premio", "ganhou", "resgate",
)  # fmt: skip
PERSONAL_DATA_TERMS = (
    "senha", "cpf", "cartão", "cartao", "cvv", "código de segurança", "codigo de seguranca",
    "token", "chave pix", "número do cartão", "numero do cartao",
)  # fmt: skip
SUSPICIOUS_TLDS = (".xyz", ".top", ".click", ".icu", ".tk", ".ml", ".ga", ".cf", ".gq", ".shop", ".live", ".buzz")
LOCAL_HOSTS = ("localhost", "127.0.0.1")
YOUNG_DOMAIN_DAYS = 30

_FALLBACK_SPEECH = {
    "scam": "Não abre esse link. Eu abri antes, longe do seu celular, e parece golpe.",
    "caution": "Vai com calma. Esse link tem coisas estranhas. Quer que eu pergunte para alguém da família?",
    "safe": "Olhei esse link antes e não vi nada estranho. Pode abrir.",
}


@dataclass(frozen=True)
class PageFacts:
    """Everything observed about a page, independent of the browser."""

    requested_url: str
    final_url: str
    title: str
    text: str
    has_password_field: bool
    downloads: int = 0
    domain_age_days: int | None = None


@dataclass
class Evaluation:
    """Score and human-readable findings for a page."""

    score: int = 0
    findings: list[str] = field(default_factory=list)
    # Stable keys of the findings, for anonymous statistics (never the URL or host).
    signals: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.score >= SCAM_THRESHOLD:
            return "scam"
        return "caution" if self.score >= CAUTION_THRESHOLD else "safe"

    def add(self, points: int, finding: str, signal: str) -> None:
        self.score = min(MAX_SCORE, self.score + points)
        self.findings.append(finding)
        self.signals.append(signal)


def _is_official(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def evaluate(facts: PageFacts) -> Evaluation:
    """Score a page from its observed facts. Pure function, no I/O.

    Args:
        facts: Observations collected by :func:`scan`.

    Returns:
        The evaluation with a 0-100 score and user-facing findings.
    """
    result = Evaluation()
    host = urlparse(facts.final_url).hostname or ""
    requested_host = urlparse(facts.requested_url).hostname or ""
    is_local = host in LOCAL_HOSTS
    text, title = facts.text.lower(), facts.title.lower()

    if host != requested_host:
        result.add(15, f"O link levou para outro endereço: {host}", "redirect")
    if not facts.final_url.startswith("https://") and not is_local:
        result.add(15, "O site não tem cadeado (sem https)", "no_https")
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host) and not is_local:
        result.add(25, "O endereço é só um número, não um nome", "ip_address")
    if "xn--" in host:
        result.add(25, "O endereço usa letras disfarçadas", "lookalike_letters")
    if host.endswith(SUSPICIOUS_TLDS):
        result.add(15, "O endereço termina de um jeito muito usado em golpes", "suspicious_tld")
    if host.count("-") >= 2 or host.count(".") >= 4:
        result.add(10, "O endereço é comprido e estranho", "odd_address")

    for brand, domains in OFFICIAL_DOMAINS.items():
        if (brand in title or brand in text[:1500]) and not _is_official(host, domains):
            result.add(35, f"A página usa o nome “{brand}”, mas o endereço não é o oficial", "brand_impersonation")
            break

    requested_data = [term for term in PERSONAL_DATA_TERMS if term in text]
    if facts.has_password_field:
        result.add(20, "Pede senha", "asks_password")
    if len(requested_data) >= 2:
        result.add(15, "Pede dados pessoais: " + ", ".join(requested_data[:3]), "asks_personal_data")
    if any(term in text for term in URGENCY_TERMS):
        result.add(10, "Usa pressa e ameaça para você agir rápido", "urgency")
    if facts.downloads:
        result.add(30, "Tentou baixar um arquivo sozinho", "auto_download")
    if facts.domain_age_days is not None and facts.domain_age_days < YOUNG_DOMAIN_DAYS:
        result.add(25, f"O site foi criado há {facts.domain_age_days} dias", "young_domain")
    return result


async def _domain_age_days(host: str) -> int | None:
    """Days since domain registration via public RDAP, or ``None`` if unknown."""
    labels = host.split(".")
    registrable = ".".join(labels[-3:] if host.endswith(".br") else labels[-2:])
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True) as client:
            response = await client.get(f"https://rdap.org/domain/{registrable}")
            for event in response.json().get("events", []):
                if event.get("eventAction") == "registration":
                    registered = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
                    return (datetime.now(UTC) - registered).days
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return None


async def scan(url: str) -> dict[str, Any]:
    """Open ``url`` in a disposable browser and report whether it looks like a scam.

    Args:
        url: Link to inspect. ``http://`` is assumed when no scheme is given.

    Returns:
        A JSON-serialisable report: verdict, score, findings, redirect chain,
        a screenshot (data URL) and the sentence Caramelo says to the user.
    """
    if not re.match(r"^https?://", url):
        url = "http://" + url
    redirect_chain: list[str] = []
    downloads: list[str] = []
    driver, browser = await launch()
    try:
        context = await browser.new_context(
            viewport={"width": 390, "height": 844}, locale="pt-BR", accept_downloads=False
        )
        page = await context.new_page()
        page.on("framenavigated", lambda f: redirect_chain.append(f.url) if f == page.main_frame else None)
        page.on("download", lambda d: downloads.append(d.suggested_filename))
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            await page.wait_for_timeout(1_200)
        except Exception as exc:  # noqa: BLE001 - any navigation failure is reported, not raised
            return {
                "url": url, "verdict": "unreachable", "score": 50, "findings": ["O link não abriu."],
                "signals": ["unreachable"],
                "speech": "Esse link não abriu. Melhor não insistir.", "error": str(exc)[:120],
            }  # fmt: skip
        host = urlparse(page.url).hostname or ""
        facts = PageFacts(
            requested_url=url,
            final_url=page.url,
            title=await page.title() or "",
            text=(await page.inner_text("body"))[:6000],
            has_password_field=await page.locator("input[type=password]").count() > 0,
            downloads=len(downloads),
            domain_age_days=None if host in LOCAL_HOSTS else await _domain_age_days(host),
        )
        screenshot = await page.screenshot(type="jpeg", quality=55)
    finally:
        await browser.close()  # the isolated session is destroyed
        await driver.stop()

    evaluation = evaluate(facts)
    speech = await llm.complete(prompts.link_verdict_speech(evaluation.verdict, evaluation.findings))
    return {
        "url": url,
        "final_url": facts.final_url,
        "host": host,
        "title": facts.title,
        "redirect_chain": list(dict.fromkeys(redirect_chain)),
        "score": evaluation.score,
        "verdict": evaluation.verdict,
        "findings": evaluation.findings,
        "signals": evaluation.signals,
        "speech": guardrails.guard_output(speech, _FALLBACK_SPEECH[evaluation.verdict]).text,
        "screenshot": "data:image/jpeg;base64," + base64.b64encode(screenshot).decode(),
        "llm_provider": llm.provider(),
    }
