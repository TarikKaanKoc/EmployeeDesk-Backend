"""Mock ERP - a stand-in for the procurement system.

A separate process with its own port, health endpoint and Kubernetes
deployment. It reads only the `erp` schema and answers for any PR number
it is asked about: an ERP does not know who is signed in to the assistant.
Scoping a result to the caller is the API's job (`modules/procurement`),
which is exactly how a real integration would have to behave.

    pdm run mock-erp          # http://127.0.0.1:8013/docs
"""

from contextlib import asynccontextmanager
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import settings
from src.app.database.connections import close_engine, get_engine
from src.app.database.models import PurchaseRequest
from src.app.database.session import get_session
from src.mock_erp.schemas import PurchaseRequestList, PurchaseRequestRecord

SERVICE = "employeedesk-mock-erp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()
    yield
    await close_engine()


app = FastAPI(
    title="Mock ERP",
    description="Synthetic procurement system used by EmployeeDesk. No real data.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

Session = Annotated[AsyncSession, Depends(get_session)]


@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE}


@app.get("/health/ready")
async def ready(session: Session):
    await session.execute(select(1))
    return {"status": "ready"}


@app.get("/purchase-requests", response_model=PurchaseRequestList)
async def list_requests(
    session: Session,
    requester_id: Optional[str] = Query(default=None, max_length=16),
    limit: int = Query(default=100, ge=1, le=500),
):
    stmt = select(PurchaseRequest)
    count = select(func.count()).select_from(PurchaseRequest)
    if requester_id:
        stmt = stmt.where(PurchaseRequest.requester_employee_id == requester_id)
        count = count.where(PurchaseRequest.requester_employee_id == requester_id)
    stmt = stmt.order_by(
        PurchaseRequest.created_date.desc(), PurchaseRequest.pr_number
    ).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    total = (await session.execute(count)).scalar_one()
    return PurchaseRequestList(
        items=[PurchaseRequestRecord.from_row(r) for r in rows], total=total
    )


@app.get("/purchase-requests/{pr_number}", response_model=PurchaseRequestRecord)
async def get_request(pr_number: str, session: Session):
    row = await session.get(PurchaseRequest, pr_number.strip().upper())
    if row is None:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return PurchaseRequestRecord.from_row(row)
