from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    #: Plain string on purpose: the synthetic directory uses the reserved
    #: `.test` domain, which a strict e-mail validator rejects.
    email: str = Field(min_length=3, max_length=120, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=256)


class TokenPair(BaseModel):
    """Returned in the body for API clients; the same pair is also set as
    HttpOnly cookies for the web client."""

    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"


class RefreshRequest(BaseModel):
    refreshToken: Optional[str] = None
