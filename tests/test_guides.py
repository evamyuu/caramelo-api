from app.services import guides


def test_gov_br_captcha_rejection_is_detected():
    assert guides.automation_rejected("Captcha inválido. Tente novamente. (ERL0000900)")
    assert not guides.automation_rejected("Identifique-se no gov.br com: Número do CPF")


def test_meu_inss_has_curated_steps():
    guide = guides.guide_for("https://meu.inss.gov.br/", "ver meu pagamento")
    assert guide.url == "https://meu.inss.gov.br/"
    assert any("Extrato de Pagamento" in step for step in guide.steps)


def test_other_sites_get_generic_steps_with_the_task():
    guide = guides.guide_for("https://www.prefeitura.sp.gov.br/", "agendar vacina")
    assert any("agendar vacina" in step for step in guide.steps)
    assert any("só você digita" in step for step in guide.steps)
