from fastapi import APIRouter

from src.app.modules.assistant.router import router as assistant_router
from src.app.modules.audit.router import router as audit_router
from src.app.modules.auth.router import router as auth_router
from src.app.modules.common.health import router as health_router
from src.app.modules.employees.router import router as employees_router
from src.app.modules.leave.router import router as leave_router
from src.app.modules.policies.router import router as policies_router
from src.app.modules.procurement.router import router as procurement_router


def create_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router, prefix="/health", tags=["health"])
    router.include_router(auth_router, prefix="/auth", tags=["auth"])
    router.include_router(employees_router, prefix="/employees", tags=["employees"])
    router.include_router(leave_router, prefix="/leave", tags=["leave"])
    router.include_router(
        procurement_router, prefix="/procurement", tags=["procurement"]
    )
    router.include_router(policies_router, prefix="/policies", tags=["policies"])
    router.include_router(assistant_router, prefix="/assistant", tags=["assistant"])
    router.include_router(audit_router, prefix="/audit", tags=["audit"])
    return router
