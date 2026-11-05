from typing import Annotated, List

from fastapi import APIRouter, Depends

from src.app.api.dependencies import CurrentEmployee, get_current_employee
from src.app.core.rate_limiter import rate_limit
from src.app.database.repository_provider import RepositoryProvider, get_repos
from src.app.modules.policies import service
from src.app.modules.policies.schemas import (
    PolicyDocumentOut,
    PolicySearchRequest,
    PolicySearchResponse,
)

router = APIRouter()

Current = Annotated[CurrentEmployee, Depends(get_current_employee)]
Repos = Annotated[RepositoryProvider, Depends(get_repos)]


@router.get(
    "", response_model=List[PolicyDocumentOut], dependencies=[rate_limit(60, 60)]
)
async def list_documents(current: Current, repos: Repos) -> List[PolicyDocumentOut]:
    return [
        PolicyDocumentOut(
            documentId=d.id, titleEn=d.title_en, titleAr=d.title_ar, clauses=n
        )
        for d, n in await service.documents(repos)
    ]


@router.post(
    "/search", response_model=PolicySearchResponse, dependencies=[rate_limit(60, 60)]
)
async def search(
    body: PolicySearchRequest, current: Current, repos: Repos
) -> PolicySearchResponse:
    return await service.search(repos, body)
