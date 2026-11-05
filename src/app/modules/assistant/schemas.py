from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from src.app.database.enums import Language
from src.app.modules.leave.schemas import LeaveRequestOut
from src.app.modules.policies.schemas import Citation


class Attachment(BaseModel):
    """Either a synthetic fixture by id (`untrusted_documents`) or raw text.
    Both are treated as untrusted data."""

    documentId: Optional[str] = Field(default=None, max_length=16)
    title: Optional[str] = Field(default=None, max_length=160)
    content: Optional[str] = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _one_of(self) -> "Attachment":
        if not self.documentId and not self.content:
            raise ValueError("documentId or content is required")
        return self


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversationId: Optional[str] = Field(default=None, max_length=32)
    language: Optional[Language] = None
    attachments: List[Attachment] = Field(default_factory=list, max_length=5)


class ToolCallOut(BaseModel):
    name: str
    status: Literal["ok", "refused", "confirmation_required", "error", "empty"]
    arguments: Dict[str, Any] = Field(default_factory=dict)
    detail: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class PendingActionOut(BaseModel):
    actionId: str
    kind: Literal["leave_request"]
    summary: str
    payload: Dict[str, Any]
    expiresAt: datetime


class ChatResponse(BaseModel):
    conversationId: str
    language: Language
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    toolCalls: List[ToolCallOut] = Field(default_factory=list)
    pendingAction: Optional[PendingActionOut] = None
    refused: bool = False
    flags: List[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    decision: Literal["confirm", "reject"] = "confirm"


class ConfirmResponse(BaseModel):
    actionId: str
    decision: Literal["confirm", "reject"]
    result: Optional[LeaveRequestOut] = None
    message: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    language: Language
    citations: Optional[List[Dict[str, Any]]] = None
    toolCalls: Optional[List[Dict[str, Any]]] = None
    flags: Optional[List[str]] = None
    createdAt: datetime


class ConversationOut(BaseModel):
    conversationId: str
    title: Optional[str]
    language: Language
    createdAt: datetime
    updatedAt: datetime
    messages: List[MessageOut] = Field(default_factory=list)
