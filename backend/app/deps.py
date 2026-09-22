from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Issue, Membership, Role, User
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    user_id = decode_token(creds.credentials) if creds else None
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_membership(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership:
    membership = db.get(Membership, (project_id, user.id))
    if membership is None:
        # 404 rather than 403 so non-members can't probe which projects exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return membership


def require_owner(membership: Membership = Depends(get_membership)) -> Membership:
    if membership.role != Role.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only project owners can do that")
    return membership


def load_issue(db: Session, issue_id: int, user: User, *, for_update: bool = False) -> Issue:
    stmt = select(Issue).where(Issue.id == issue_id)
    if for_update:
        stmt = stmt.with_for_update(of=Issue)
    issue = db.scalar(stmt)
    if issue is None or db.get(Membership, (issue.project_id, user.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    return issue
