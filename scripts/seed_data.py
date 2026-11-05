"""Load the synthetic data pack (xlsx) into Postgres.

Sheet -> table:
    Employees             -> employees
    Identity_Map          -> identities
    Leave_Balances        -> leave_balances
    Leave_Requests        -> leave_requests
    Policy_Knowledge      -> policy_documents + policy_clauses
    Untrusted_Documents   -> untrusted_documents
    Assistant_Test_Cases  -> assistant_test_cases
    Purchase_Requests     -> erp.purchase_requests

Expected_Result on Identity_Map is derived data ("Allow E1001 only" /
"Deny inactive identity") and is not stored: it follows from
employees.employment_status, which the access tests read directly.
"""

import argparse
import asyncio
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List

import openpyxl
from loguru import logger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.core.config import settings  # noqa: E402
from src.app.database.connections import close_engine, get_session_factory  # noqa: E402
from src.app.database.enums import (  # noqa: E402
    DocumentContentType,
    EmploymentStatus,
    Language,
    LeaveReasonCategory,
    LeaveRequestStatus,
    LeaveType,
    PolicyDomain,
    PurchaseRequestStatus,
)
from src.app.database.models import (  # noqa: E402
    AssistantTestCase,
    Employee,
    Identity,
    LeaveBalance,
    LeaveRequest,
    PolicyClause,
    PolicyDocument,
    PurchaseRequest,
    UntrustedDocument,
)

DEFAULT_WORKBOOK = (
    ROOT / "seed" / "Tarik_Employee_Services_Assistant_Synthetic_Data_Expanded.xlsx"
)

#: Sheets carry two banner rows above the header row.
HEADER_ROW = 3

LANGUAGE = {"English": Language.en, "Arabic": Language.ar}
EMPLOYMENT = {"Active": EmploymentStatus.active, "Inactive": EmploymentStatus.inactive}
LEAVE_TYPE = {"Annual": LeaveType.annual, "Sick": LeaveType.sick}
LEAVE_STATUS = {s.value.capitalize(): s for s in LeaveRequestStatus}
REASON = {r.value.capitalize(): r for r in LeaveReasonCategory}
PR_STATUS = {
    "Under Review": PurchaseRequestStatus.under_review,
    "Approved": PurchaseRequestStatus.approved,
    "Returned": PurchaseRequestStatus.returned,
    "Rejected": PurchaseRequestStatus.rejected,
}
CONTENT_TYPE = {c.value.upper(): c for c in DocumentContentType}

POLICY_DOCUMENTS = {
    "HR": dict(
        id=PolicyDomain.hr,
        title_en="Human Resources Policy",
        title_ar="سياسة الموارد البشرية",
    ),
    "Procurement": dict(
        id=PolicyDomain.procurement,
        title_en="Procurement Policy",
        title_ar="سياسة المشتريات",
    ),
    "Information Security": dict(
        id=PolicyDomain.information_security,
        title_en="Information Security Policy",
        title_ar="سياسة أمن المعلومات",
    ),
}


def read_sheet(wb, name: str) -> List[Dict[str, Any]]:
    ws = wb[name]
    rows = list(ws.iter_rows(min_row=HEADER_ROW, values_only=True))
    header = [str(h).strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not any(c not in (None, "") for c in r):
            continue
        out.append(dict(zip(header, r, strict=False)))
    return out


def as_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):  # Excel serial
        from datetime import timedelta

        return date(1899, 12, 30) + timedelta(days=int(v))
    return date.fromisoformat(str(v))


def as_bool(v) -> bool:
    return str(v).strip() in ("1", "true", "True", "yes")


def as_dec(v) -> Decimal:
    return Decimal(str(v))


def at_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


async def upsert(
    session: AsyncSession, model, rows: Iterable[dict], key: List[str]
) -> int:
    rows = list(rows)
    if not rows:
        return 0
    stmt = insert(model).values(rows)
    update_cols = {
        c.name: getattr(stmt.excluded, c.name)
        for c in model.__table__.columns
        if c.name not in key and not c.computed and c.name in rows[0]
    }
    stmt = stmt.on_conflict_do_update(index_elements=key, set_=update_cols)
    await session.execute(stmt)
    return len(rows)


async def load(session: AsyncSession, wb) -> Dict[str, int]:
    counts: Dict[str, int] = {}

    employees = [
        dict(
            id=r["Employee_ID"],
            display_name_en=r["Display_Name_EN"],
            display_name_ar=r["Display_Name_AR"],
            department=r["Department"],
            role=r["Role"],
            work_location=r["Work_Location"],
            email_alias=r["Email_Alias"],
            employment_status=EMPLOYMENT[r["Employment_Status"]],
        )
        for r in read_sheet(wb, "Employees")
    ]
    counts["employees"] = await upsert(session, Employee, employees, ["id"])

    identities = [
        dict(
            sign_in_subject=r["SignIn_Subject"],
            employee_id=r["Employee_ID"],
            tenant=r["Tenant"],
        )
        for r in read_sheet(wb, "Identity_Map")
    ]
    counts["identities"] = await upsert(
        session, Identity, identities, ["sign_in_subject"]
    )

    balances = [
        dict(
            employee_id=r["Employee_ID"],
            leave_type=LEAVE_TYPE[r["Leave_Type"]],
            entitled_days=as_dec(r["Entitled_Days"]),
            used_days=as_dec(r["Used_Days"]),
            pending_days=as_dec(r["Pending_Days"]),
            as_of_date=as_date(r["As_Of_Date"]),
        )
        for r in read_sheet(wb, "Leave_Balances")
    ]
    for r, src in zip(balances, read_sheet(wb, "Leave_Balances"), strict=True):
        expected = r["entitled_days"] - r["used_days"] - r["pending_days"]
        if expected != as_dec(src["Available_Days"]):
            raise ValueError(f"Leave_Balances integrity: {src}")
    counts["leave_balances"] = await upsert(
        session, LeaveBalance, balances, ["employee_id", "leave_type"]
    )

    requests = [
        dict(
            id=r["Request_ID"],
            employee_id=r["Employee_ID"],
            leave_type=LEAVE_TYPE[r["Leave_Type"]],
            start_date=as_date(r["Start_Date"]),
            end_date=as_date(r["End_Date"]),
            reason_category=REASON[r["Reason_Category"]],
            status=LEAVE_STATUS[r["Status"]],
            confirmation_recorded=as_bool(r["Confirmation_Recorded"]),
            created_at=at_utc(as_date(r["Created_At"])),
        )
        for r in read_sheet(wb, "Leave_Requests")
    ]
    for r, src in zip(requests, read_sheet(wb, "Leave_Requests"), strict=True):
        if (r["end_date"] - r["start_date"]).days + 1 != int(src["Days"]):
            raise ValueError(f"Leave_Requests days integrity: {src}")
    counts["leave_requests"] = await upsert(session, LeaveRequest, requests, ["id"])

    counts["policy_documents"] = await upsert(
        session,
        PolicyDocument,
        list(POLICY_DOCUMENTS.values()),
        ["id"],
    )
    clauses = [
        dict(
            id=r["Policy_ID"],
            document_id=POLICY_DOCUMENTS[r["Domain"]]["id"],
            section=str(r["Section"]),
            language=LANGUAGE[r["Language"]],
            question_theme=r["Question_Theme"],
            text=r["Policy_Text"],
            effective_from=as_date(r["Effective_From"]),
            answerable=as_bool(r["Answerable"]),
        )
        for r in read_sheet(wb, "Policy_Knowledge")
    ]
    counts["policy_clauses"] = await upsert(session, PolicyClause, clauses, ["id"])

    docs = [
        dict(
            id=r["Document_ID"],
            title=r["Document_Title"],
            content_type=CONTENT_TYPE[r["Content_Type"]],
            visible_content=r["Visible_Content"],
            embedded_instruction=r["Embedded_Instruction_Test"],
            expected_behaviour=r["Expected_Assistant_Behaviour"],
        )
        for r in read_sheet(wb, "Untrusted_Documents")
    ]
    counts["untrusted_documents"] = await upsert(
        session, UntrustedDocument, docs, ["id"]
    )

    cases = [
        dict(
            id=r["Test_ID"],
            signed_in_employee_id=r["SignedIn_Employee_ID"],
            language=LANGUAGE[r["Language"]],
            user_request=r["User_Request"],
            expected_tool_action=r["Expected_Tool_Action"],
            expected_result=r["Expected_Result"],
            expected_citation=r["Expected_Citation"],
            write_confirmation_required=as_bool(r["Write_Confirmation_Required"]),
        )
        for r in read_sheet(wb, "Assistant_Test_Cases")
    ]
    counts["assistant_test_cases"] = await upsert(
        session, AssistantTestCase, cases, ["id"]
    )

    prs = [
        dict(
            pr_number=r["PR_Number"],
            requester_employee_id=r["Requester_Employee_ID"],
            department=r["Department"],
            business_purpose=r["Business_Purpose"],
            amount_qar=as_dec(r["Amount_QAR"]),
            status=PR_STATUS[r["Status"]],
            current_step=r["Current_Step"],
            created_date=as_date(r["Created_Date"]),
            last_updated=as_date(r["Last_Updated"]),
            mock_reference=r["Mock_Reference"],
        )
        for r in read_sheet(wb, "Purchase_Requests")
    ]
    counts["erp.purchase_requests"] = await upsert(
        session, PurchaseRequest, prs, ["pr_number"]
    )
    return counts


def embedding_input(clause: PolicyClause) -> str:
    """What gets embedded: theme + clause. The synthetic Arabic clauses
    differ from each other only by their (English) theme word, so the
    theme has to be part of the vector for an Arabic paraphrase to land
    on the right clause."""
    return f"{clause.question_theme}: {clause.text}"


async def embed_clauses(session: AsyncSession) -> int:
    """Fill `policy_clauses.embedding` where it is NULL. Skipped (with a
    warning) when no Azure OpenAI endpoint is configured."""
    if not settings.embeddings_configured:
        logger.warning(
            "AZURE_OPENAI_BASE_URL / API_KEY not set - skipping embeddings (keyword search still works)"
        )
        return 0
    from sqlalchemy import select

    from src.app.core.llm import client as llm_client

    client = llm_client()
    rows = (
        (
            await session.execute(
                select(PolicyClause).where(PolicyClause.embedding.is_(None))
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    resp = await client.embeddings.create(
        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        input=[embedding_input(r) for r in rows],
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
    for row, item in zip(rows, resp.data, strict=True):
        row.embedding = item.embedding
        row.embedding_model = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
    return len(rows)


async def main(path: Path, embeddings: bool) -> None:
    logger.info(f"Loading {path.name}")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    async with get_session_factory()() as session:
        async with session.begin():
            counts = await load(session, wb)
            embedded = await embed_clauses(session) if embeddings else 0
    await close_engine()
    for k, v in counts.items():
        logger.info(f"  {k:<24} {v:>4} rows")
    logger.info(f"  {'embeddings':<24} {embedded:>4} filled")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook", nargs="?", default=DEFAULT_WORKBOOK, type=Path)
    ap.add_argument("--no-embeddings", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.workbook, embeddings=not a.no_embeddings))
