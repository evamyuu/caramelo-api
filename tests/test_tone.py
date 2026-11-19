import pytest

from app.ai.tone import respectful


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Oi, vovó! O INSS não liga pedindo senha.", "Oi, Maria! O INSS não liga pedindo senha."),
        ("Oi, Dona Maria! Au, liga para o número antigo.", "Oi, Maria! Liga para o número antigo."),
        ("Calma, querida, eu ajudo.", "Calma, eu ajudo."),
        ("Vovó Maria, toque em Entrar.", "Maria, toque em Entrar."),
        ("Se precisar de mais alguma coisa, é só latir!", "Se precisar de mais alguma coisa, é só me chamar!"),
        ("Maria, você tem R$ 1.240,37 a receber.", "Maria, você tem R$ 1.240,37 a receber."),
        ("Autorize só se for você.", "Autorize só se for você."),  # "au" inside a word stays
    ],
)
def test_pet_names_and_barking_are_removed(reply, expected):
    assert respectful(reply) == expected
