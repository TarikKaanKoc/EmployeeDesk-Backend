from typing import Any, List, Optional

from pydantic import BaseModel


class ApiErrorResponse(BaseModel):
    errorCode: str
    message: str
    errors: Optional[List[Any]] = None
