from src.app.api.dependencies import CurrentEmployee
from src.app.database.models import Employee


async def me(current: CurrentEmployee) -> Employee:
    return current.employee
