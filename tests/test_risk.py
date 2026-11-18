from app.services.risk import RiskLevel, assess_call


def test_classic_fake_bank_call_is_a_scam():
    result = assess_call({
        "missing_verified_origin": True, "unknown_caller": True, "asks_for_code_or_password": True,
        "creates_urgency": True, "claims_bank_or_government": True,
    })
    assert result.score == 92
    assert result.level is RiskLevel.SCAM
    assert result.notify_family


def test_unknown_caller_alone_is_safe():
    assert assess_call({"unknown_caller": True}).level is RiskLevel.SAFE


def test_score_is_capped_and_unknown_signals_are_ignored():
    result = assess_call({key: True for key in (
        "missing_verified_origin", "asks_for_code_or_password", "creates_urgency", "recent_sim_swap",
        "reported_in_region", "claims_bank_or_government", "not_a_real_signal")})
    assert result.score == 100
