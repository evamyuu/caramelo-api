"""Grounded assistant answers (retrieval-augmented generation).

Flow: retrieve curated chunks, then let the model phrase an answer using only
them. With no model, or if it fails, the best chunk is returned as is, so the
answer is always grounded in reviewed content and always cites its source.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai import client as llm
from app.ai import prompts
from app.db.repositories.knowledge import KnowledgeChunk, KnowledgeRepository

logger = logging.getLogger(__name__)
NO_ANSWER = "Isso eu ainda não sei responder direito. Quer que eu chame alguém da família para ajudar?"


@dataclass(frozen=True)
class AssistantAnswer:
    speech: str
    sources: list[str]
    grounded: bool


async def _retrieve(knowledge: KnowledgeRepository, question: str) -> list[KnowledgeChunk]:
    try:
        return await knowledge.search(question)
    except Exception:  # retrieval must never break the conversation
        logger.exception("Knowledge search failed")
        return []


async def answer(question: str, knowledge: KnowledgeRepository) -> AssistantAnswer:
    """Answer a free-form question from the knowledge base."""
    chunks = await _retrieve(knowledge, question)
    if not chunks:
        return AssistantAnswer(NO_ANSWER, [], grounded=False)
    reply = await llm.complete(prompts.grounded_answer(question, [(c.title, c.text) for c in chunks]))
    sources = list(dict.fromkeys(chunk.source for chunk in chunks))
    return AssistantAnswer((reply or chunks[0].text).strip(), sources, grounded=True)
