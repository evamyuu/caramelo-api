from app.db.repositories.knowledge import InMemoryKnowledgeRepository
from app.services import assistant


async def test_retrieval_finds_the_relevant_chunk():
    chunks = await InMemoryKnowledgeRepository().search("preciso fazer prova de vida no banco?")
    assert chunks[0].title == "Prova de vida do INSS"


async def test_answer_is_grounded_and_cites_its_source_without_a_model():
    reply = await assistant.answer("como funciona a meia-entrada no cinema?", InMemoryKnowledgeRepository())
    assert reply.grounded and "metade" in reply.speech
    assert reply.sources[0].startswith("Estatuto da Pessoa Idosa")


async def test_unknown_subject_is_not_answered():
    reply = await assistant.answer("xyzzy", InMemoryKnowledgeRepository())
    assert reply.grounded is False and reply.sources == []


async def test_a_single_shared_word_does_not_match_a_longer_question():
    assert await InMemoryKnowledgeRepository().search("receita de bolo de chocolate") == []


async def test_fallback_is_used_when_the_primary_search_fails():
    from app.db.repositories.knowledge import FallbackKnowledgeRepository

    class Failing:
        async def search(self, query, limit=3):
            raise RuntimeError("rate limited")

    chunks = await FallbackKnowledgeRepository(Failing(), InMemoryKnowledgeRepository()).search("golpe do motoboy")
    assert chunks[0].title == "Golpe do motoboy"
