"""Call risk scoring.

A transparent weighted-signal model: every point of the score can be explained
to the user and reviewed on request (LGPD art. 20, automated decisions).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MAX_SCORE = 100
SCAM_THRESHOLD = 60
CAUTION_THRESHOLD = 30


class RiskLevel(StrEnum):
    """Outcome bucket shown to the user."""

    SAFE = "safe"
    CAUTION = "caution"
    SCAM = "scam"


@dataclass(frozen=True)
class Signal:
    """One observable fact about an incoming call."""

    weight: int
    label: str  # user-facing, Brazilian Portuguese


CALL_SIGNALS: dict[str, Signal] = {
    "missing_verified_origin": Signal(25, "Sem o selo Origem Verificada"),
    "unknown_caller": Signal(10, "Número desconhecido"),
    "asks_for_code_or_password": Signal(30, "Pede código ou senha"),
    "creates_urgency": Signal(15, "Cria urgência"),
    "claims_bank_or_government": Signal(12, "Diz ser do banco ou do governo"),
    "recent_sim_swap": Signal(20, "Seu chip foi trocado há pouco tempo"),
    "foreign_area_code": Signal(5, "DDD de outra região"),
    "reported_in_region": Signal(15, "Número já denunciado na sua região"),
}

_SPEECH = {
    RiskLevel.SCAM: "Maria, espera. Essa ligação parece golpe. Não fale nenhum código nem senha.",
    RiskLevel.CAUTION: "Vamos com calma. Não conheço esse número. Se pedirem código, desliga.",
    RiskLevel.SAFE: "Pode atender, tá tudo bem.",
}


@dataclass(frozen=True)
class CallRiskAssessment:
    """Result of scoring one call."""

    score: int
    level: RiskLevel
    reasons: list[str]
    speech: str
    notify_family: bool


def level_for(score: int) -> RiskLevel:
    """Map a 0-100 score to a risk level."""
    if score >= SCAM_THRESHOLD:
        return RiskLevel.SCAM
    if score >= CAUTION_THRESHOLD:
        return RiskLevel.CAUTION
    return RiskLevel.SAFE


def assess_call(signals: dict[str, bool]) -> CallRiskAssessment:
    """Score an incoming call from its active signals.

    Args:
        signals: Signal key to whether it was observed. Unknown keys are ignored.

    Returns:
        The assessment, with the score capped at ``MAX_SCORE``.
    """
    active = [key for key, observed in signals.items() if observed and key in CALL_SIGNALS]
    score = min(MAX_SCORE, sum(CALL_SIGNALS[key].weight for key in active))
    level = level_for(score)
    return CallRiskAssessment(
        score=score,
        level=level,
        reasons=[CALL_SIGNALS[key].label for key in active],
        speech=_SPEECH[level],
        notify_family=level is RiskLevel.SCAM,
    )
