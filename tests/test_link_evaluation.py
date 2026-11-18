from app.services.link_scanner import PageFacts, evaluate


def _facts(**overrides):
    base = dict(requested_url="https://example.com/", final_url="https://example.com/", title="Example",
                text="Bem-vindo", has_password_field=False)
    return PageFacts(**{**base, **overrides})


def test_clean_page_is_safe():
    assert evaluate(_facts()).verdict == "safe"


def test_bank_impersonation_with_password_and_urgency_is_a_scam():
    result = evaluate(_facts(
        requested_url="http://bit.ly/x", final_url="http://banco-seguro-app.xyz/login",
        title="Banco do Brasil", text="URGENTE: sua conta será bloqueada. Informe CPF e senha.",
        has_password_field=True))
    assert result.verdict == "scam"
    assert any("oficial" in finding for finding in result.findings)


def test_official_domain_is_not_flagged_as_impersonation():
    result = evaluate(_facts(requested_url="https://www.bb.com.br/", final_url="https://www.bb.com.br/",
                             title="Banco do Brasil", has_password_field=True))
    assert result.verdict == "safe"


def test_young_domain_raises_the_score():
    assert evaluate(_facts(domain_age_days=2)).score == 25
