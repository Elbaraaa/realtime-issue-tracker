from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import Priority, Role, Status


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(_Out):
    id: int
    email: EmailStr
    name: str


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProjectIn(BaseModel):
    # Short uppercase prefix used in issue keys, e.g. WEB-12.
    key: str = Field(pattern=r"^[A-Z][A-Z0-9]{1,9}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=5000)


class ProjectOut(_Out):
    id: int
    key: str
    name: str
    description: str
    created_at: datetime


class MemberIn(BaseModel):
    email: EmailStr


class MemberOut(_Out):
    user: UserOut
    role: Role


class IssueIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=20000)
    status: Status = Status.todo
    priority: Priority = Priority.medium
    assignee_id: int | None = None


class IssuePatch(BaseModel):
    """Partial update. Only fields present in the request body are applied."""

    version: int
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=20000)
    status: Status | None = None
    priority: Priority | None = None
    assignee_id: int | None = None
    position: float | None = None


class IssueOut(_Out):
    id: int
    project_id: int
    number: int
    title: str
    description: str
    status: Status
    priority: Priority
    assignee: UserOut | None
    reporter: UserOut
    position: float
    version: int
    created_at: datetime
    updated_at: datetime


class IssuePage(BaseModel):
    items: list[IssueOut]
    total: int


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class CommentOut(_Out):
    id: int
    issue_id: int
    author: UserOut
    body: str
    created_at: datetime


class ActivityOut(_Out):
    id: int
    issue_id: int | None
    actor: UserOut
    kind: str
    data: dict[str, Any]
    created_at: datetime
