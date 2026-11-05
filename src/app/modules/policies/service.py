"""Policy documents and search. Search returns citations, never prose:
composing an answer from them is the assistant's job, and only from
clauses marked answerable."""

from typing import List, Tuple

from src.app.core import llm
from src.app.core.config import settings
from src.app.database.models import PolicyClause, PolicyDocument
from src.app.database.repository_provider import RepositoryProvider
from src.app.modules.policies.schemas import (
    Citation,
    PolicyHit,
    PolicySearchRequest,
    PolicySearchResponse,
)


def citation(c: PolicyClause) -> Citation:
    return Citation(
        policyId=c.id,
        documentId=c.document_id,
        section=c.section,
        language=c.language,
        theme=c.question_theme,
        text=c.text,
        effectiveFrom=c.effective_from,
        answerable=c.answerable,
    )


async def documents(repos: RepositoryProvider) -> List[Tuple[PolicyDocument, int]]:
    return await repos.policies.documents()


async def search(
    repos: RepositoryProvider, body: PolicySearchRequest
) -> PolicySearchResponse:
    vectors = await llm.embed([body.query])
    embedding = vectors[0] if vectors else None
    rows = await repos.policies.search(
        body.query, language=body.language, limit=body.limit, embedding=embedding
    )
    hits = [
        PolicyHit(citation=citation(c), score=s, keywordScore=k, vectorScore=v)
        for c, s, k, v in rows
        if k > 0 or (v is not None and v >= settings.POLICY_MIN_VECTOR_SCORE)
    ]
    return PolicySearchResponse(
        query=body.query,
        mode="hybrid" if embedding is not None else "keyword",
        hits=hits,
    )
