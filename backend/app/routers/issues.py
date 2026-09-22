from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import record
from ..db import get_db
from ..deps import get_current_user, get_membership, load_issue
from ..events import publish_activity
from ..models import ActivityEvent, Issue, Membership, Project, Role, Status, User
from ..schemas import ActivityOut, IssueIn, IssueOut, IssuePage, IssuePatch

router = APIRouter(tags=["issues"])

_POSITION_GAP = 1024.0
_NOT_NULL = {"title", "description", "status", "priority", "position"}


def _ensure_member(db: Session, project_id: int, user_id: int | None) -> None:
    if user_id is not None and db.get(Membership, (project_id, user_id)) is None:
        raise HTTPException(422, "Assignee must be a project member")


def _next_position(db: Session, project_id: int, column: Status) -> float:
    last = db.scalar(
        select(func.max(Issue.position)).where(
            Issue.project_id == project_id, Issue.status == column
        )
    )
    return (last or 0.0) + _POSITION_GAP


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


@router.get("/projects/{project_id}/issues", response_model=IssuePage)
def list_issues(
    project_id: int,
    status_: Status | None = Query(None, alias="status"),
    assignee_id: int | None = None,
    q: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Membership = Depends(get_membership),
    db: Session = Depends(get_db),
):
    stmt = select(Issue).where(Issue.project_id == project_id)
    if status_ is not None:
        stmt = stmt.where(Issue.status == status_)
    if assignee_id is not None:
        stmt = stmt.where(Issue.assignee_id == assignee_id)
    if q:
        stmt = stmt.where(Issue.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Issue.position, Issue.id).limit(limit).offset(offset)).all()
    return IssuePage(items=[IssueOut.model_validate(i) for i in items], total=total or 0)


@router.post(
    "/projects/{project_id}/issues", response_model=IssueOut, status_code=status.HTTP_201_CREATED
)
def create_issue(
    project_id: int,
    body: IssueIn,
    membership: Membership = Depends(get_membership),
    db: Session = Depends(get_db),
):
    _ensure_member(db, project_id, body.assignee_id)
    # Lock the project row so concurrent creates get distinct, gapless numbers.
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    project.issue_seq += 1
    issue = Issue(
        project_id=project_id,
        number=project.issue_seq,
        reporter_id=membership.user_id,
        position=_next_position(db, project_id, body.status),
        **body.model_dump(),
    )
    db.add(issue)
    db.flush()
    ev = record(
        db,
        project_id=project_id,
        issue_id=issue.id,
        actor_id=membership.user_id,
        kind="issue_created",
        data={"number": issue.number, "title": issue.title},
    )
    db.commit()
    publish_activity(ev)
    db.refresh(issue)
    return IssueOut.model_validate(issue)


@router.get("/issues/{issue_id}", response_model=IssueOut)
def get_issue(issue_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return IssueOut.model_validate(load_issue(db, issue_id, user))


@router.patch("/issues/{issue_id}", response_model=IssueOut)
def update_issue(
    issue_id: int,
    body: IssuePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    issue = load_issue(db, issue_id, user, for_update=True)
    if body.version != issue.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This issue was changed by someone else. Reload it and try again.",
        )

    changes: dict[str, dict[str, Any]] = {}
    for field in body.model_fields_set - {"version"}:
        new = getattr(body, field)
        if new is None and field in _NOT_NULL:
            raise HTTPException(422, f"{field} can't be null")
        if field == "assignee_id":
            _ensure_member(db, issue.project_id, new)
        old = getattr(issue, field)
        if old != new:
            setattr(issue, field, new)
            changes[field] = {"from": _plain(old), "to": _plain(new)}

    if not changes:
        return IssueOut.model_validate(issue)

    issue.version += 1
    ev = record(
        db,
        project_id=issue.project_id,
        issue_id=issue.id,
        actor_id=user.id,
        kind="issue_updated",
        data={"number": issue.number, "changes": changes},
    )
    db.commit()
    publish_activity(ev)
    db.refresh(issue)
    return IssueOut.model_validate(issue)


@router.delete("/issues/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_issue(
    issue_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    issue = load_issue(db, issue_id, user, for_update=True)
    membership = db.get(Membership, (issue.project_id, user.id))
    if issue.reporter_id != user.id and membership.role != Role.owner:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the reporter or a project owner can delete it"
        )
    # The issue's own activity cascades away, so log the deletion at project level.
    ev = record(
        db,
        project_id=issue.project_id,
        actor_id=user.id,
        kind="issue_deleted",
        data={"issue_id": issue.id, "number": issue.number, "title": issue.title},
    )
    db.delete(issue)
    db.commit()
    publish_activity(ev)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/issues/{issue_id}/activity", response_model=list[ActivityOut])
def issue_activity(
    issue_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    issue = load_issue(db, issue_id, user)
    stmt = (
        select(ActivityEvent)
        .where(ActivityEvent.issue_id == issue.id)
        .order_by(ActivityEvent.created_at, ActivityEvent.id)
    )
    return db.scalars(stmt).all()
