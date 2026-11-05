from src.app.database.base_repository import BaseRepository
from src.app.database.models import Employee


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee
