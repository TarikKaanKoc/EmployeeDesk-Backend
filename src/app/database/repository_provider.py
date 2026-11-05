"""One repository per table, built lazily on the request's session."""

from functools import cached_property
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.session import get_session


class RepositoryProvider:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @cached_property
    def employees(self):
        from src.app.modules.employees.repository import EmployeeRepository

        return EmployeeRepository(self.session)

    @cached_property
    def identities(self):
        from src.app.modules.auth.repository import IdentityRepository

        return IdentityRepository(self.session)

    @cached_property
    def leave(self):
        from src.app.modules.leave.repository import LeaveRepository

        return LeaveRepository(self.session)

    @cached_property
    def conversations(self):
        from src.app.modules.assistant.repository import ConversationRepository

        return ConversationRepository(self.session)

    @cached_property
    def audit(self):
        from src.app.modules.audit.repository import AuditRepository

        return AuditRepository(self.session)

    @cached_property
    def untrusted_documents(self):
        from src.app.modules.assistant.repository import UntrustedDocumentRepository

        return UntrustedDocumentRepository(self.session)

    @cached_property
    def policies(self):
        from src.app.modules.policies.repository import PolicyRepository

        return PolicyRepository(self.session)


async def get_repos(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RepositoryProvider:
    return RepositoryProvider(session)
