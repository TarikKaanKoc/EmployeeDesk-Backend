"""Retrieval over `policy_clauses`.

One SQL statement scores every clause by keyword rank (tsvector, `simple`
config so Arabic and English tokens are matched as written) and, when a
query embedding is given, by cosine similarity through pgvector. The two
are combined in SQL so the top-k is decided by the database, not by
merging two lists in Python.
"""

from typing import List, Optional, Sequence, Tuple

from sqlalchemy import Float, cast, func, literal, or_, select
from sqlalchemy.orm import joinedload

from src.app.database.base_repository import BaseRepository
from src.app.database.enums import Language
from src.app.database.models import PolicyClause, PolicyDocument

#: Weight of the vector score when one is available. Keyword rank is
#: reliable for the short, literal clauses in this corpus; the vector is
#: there to catch paraphrase, not to override an exact hit.
VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4


class PolicyRepository(BaseRepository[PolicyClause]):
    model = PolicyClause

    async def documents(self) -> List[Tuple[PolicyDocument, int]]:
        stmt = (
            select(PolicyDocument, func.count(PolicyClause.id))
            .outerjoin(PolicyClause, PolicyClause.document_id == PolicyDocument.id)
            .group_by(PolicyDocument.id)
            .order_by(PolicyDocument.id)
        )
        return [(doc, n) for doc, n in (await self.session.execute(stmt)).all()]

    async def clauses(self, policy_ids: Sequence[str]) -> List[PolicyClause]:
        if not policy_ids:
            return []
        stmt = select(PolicyClause).where(PolicyClause.id.in_(policy_ids))
        return list((await self.session.execute(stmt)).scalars())

    async def search(
        self,
        query: str,
        *,
        language: Optional[Language],
        limit: int,
        embedding: Optional[List[float]],
    ) -> List[Tuple[PolicyClause, float, float, Optional[float]]]:
        """Rows of (clause, combined score, keyword score, vector score)."""
        tsq = func.plainto_tsquery("simple", query)
        kw = func.coalesce(func.ts_rank_cd(PolicyClause.tsv, tsq), 0.0)
        if embedding is not None:
            vec = 1.0 - PolicyClause.embedding.cosine_distance(embedding)
            vec = func.coalesce(vec, 0.0)
            score = KEYWORD_WEIGHT * kw + VECTOR_WEIGHT * vec
        else:
            vec = cast(literal(None), Float)
            score = kw
        stmt = select(
            PolicyClause, score.label("score"), kw.label("kw"), vec.label("vec")
        ).options(joinedload(PolicyClause.document))
        if language is not None:
            stmt = stmt.where(PolicyClause.language == language)
        if embedding is None:
            stmt = stmt.where(PolicyClause.tsv.op("@@")(tsq))
        else:
            stmt = stmt.where(
                or_(PolicyClause.tsv.op("@@")(tsq), PolicyClause.embedding.is_not(None))
            )
        stmt = stmt.order_by(score.desc(), PolicyClause.id).limit(limit)
        rows = (await self.session.execute(stmt)).all()
        return [
            (c, float(s), float(k), (float(v) if v is not None else None))
            for c, s, k, v in rows
        ]
