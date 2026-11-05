from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from src.app.database.enums import Language, PolicyDomain


class PolicyDocumentOut(BaseModel):
    documentId: PolicyDomain
    titleEn: str
    titleAr: str
    clauses: int


class Citation(BaseModel):
    """What an answer points at. `policyId` + `section` + `language` name
    one clause exactly; `text` is the clause itself so a reader can check
    the claim without another call."""

    policyId: str
    documentId: PolicyDomain
    section: str
    language: Language
    theme: str
    text: str
    effectiveFrom: date
    answerable: bool


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    language: Optional[Language] = Field(
        default=None, description="Restrict to one language; default searches both."
    )
    limit: int = Field(default=5, ge=1, le=20)


class PolicyHit(BaseModel):
    citation: Citation
    score: float
    keywordScore: float
    vectorScore: Optional[float] = None


class PolicySearchResponse(BaseModel):
    query: str
    mode: str = Field(description="'hybrid' when embeddings were used, else 'keyword'")
    hits: List[PolicyHit]
