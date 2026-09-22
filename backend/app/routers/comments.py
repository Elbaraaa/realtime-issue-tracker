from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record
from ..db import get_db
from ..deps import get_current_user, load_issue
from ..events import publish_activity
from ..models import Comment, User
from ..schemas import CommentIn, CommentOut

router = APIRouter(prefix="/issues/{issue_id}/comments", tags=["comments"])


@router.get("", response_model=list[CommentOut])
def list_comments(
    issue_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    load_issue(db, issue_id, user)
    stmt = select(Comment).where(Comment.issue_id == issue_id).order_by(Comment.id)
    return db.scalars(stmt).all()


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    issue_id: int,
    body: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    issue = load_issue(db, issue_id, user)
    comment = Comment(issue_id=issue.id, author_id=user.id, body=body.body)
    db.add(comment)
    db.flush()
    ev = record(
        db,
        project_id=issue.project_id,
        issue_id=issue.id,
        actor_id=user.id,
        kind="comment_added",
        data={"number": issue.number, "comment_id": comment.id},
    )
    db.commit()
    publish_activity(ev)
    db.refresh(comment)
    return CommentOut.model_validate(comment)
