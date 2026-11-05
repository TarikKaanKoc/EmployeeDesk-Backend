from datetime import datetime

from pydantic import BaseModel

from src.app.database.enums import EmploymentStatus
from src.app.database.models import Employee


class EmployeeMe(BaseModel):
    """The caller's own record. There is no schema for "an employee" in
    general because no endpoint returns one."""

    employeeId: str
    displayNameEn: str
    displayNameAr: str
    department: str
    role: str
    workLocation: str
    email: str
    employmentStatus: EmploymentStatus
    createdAt: datetime

    @classmethod
    def from_row(cls, row: Employee) -> "EmployeeMe":
        return cls(
            employeeId=row.id,
            displayNameEn=row.display_name_en,
            displayNameAr=row.display_name_ar,
            department=row.department,
            role=row.role,
            workLocation=row.work_location,
            email=row.email_alias,
            employmentStatus=row.employment_status,
            createdAt=row.created_at,
        )
