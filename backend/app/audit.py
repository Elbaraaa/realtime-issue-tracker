from typing import Any

from sqlalchemy.orm import Session

from .models import ActivityEvent


def record(
    db: Session,
    *,
    project_id: int,
    actor_id: int,
    kind: str,
    issue_id: int | None = None,
    data: dict[str, Any] | None = None,
) -> ActivityEvent:
    """Stage an audit row in the caller's transaction. Publish it only after commit."""
    event = ActivityEvent(
        project_id=project_id, issue_id=issue_id, actor_id=actor_id, kind=kind, data=data or {}
    )
    db.add(event)
    return event
