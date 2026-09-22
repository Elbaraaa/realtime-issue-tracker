from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record
from ..db import get_db
from ..deps import get_current_user, get_membership, require_owner
from ..events import publish_activity
from ..models import Membership, Project, Role, User
from ..schemas import MemberIn, MemberOut, ProjectIn, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Project).join(Membership).where(Membership.user_id == user.id).order_by(Project.name)
    )
    return db.scalars(stmt).all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if db.scalar(select(Project.id).where(Project.key == body.key)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Project key {body.key} is taken")
    project = Project(**body.model_dump())
    project.memberships.append(Membership(user_id=user.id, role=Role.owner))
    db.add(project)
    db.flush()
    record(db, project_id=project.id, actor_id=user.id, kind="project_created")
    db.commit()
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(membership: Membership = Depends(get_membership)):
    return membership.project


@router.get("/{project_id}/members", response_model=list[MemberOut])
def list_members(
    project_id: int,
    _: Membership = Depends(get_membership),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Membership)
        .where(Membership.project_id == project_id)
        .join(Membership.user)
        .order_by(User.name)
    )
    return db.scalars(stmt).all()


@router.post("/{project_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: int,
    body: MemberIn,
    owner: Membership = Depends(require_owner),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account with that email")
    if db.get(Membership, (project_id, user.id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member")
    membership = Membership(project_id=project_id, user_id=user.id, role=Role.member)
    db.add(membership)
    ev = record(
        db,
        project_id=project_id,
        actor_id=owner.user_id,
        kind="member_added",
        data={"user_id": user.id, "name": user.name},
    )
    db.commit()
    publish_activity(ev)
    return membership


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    project_id: int,
    user_id: int,
    owner: Membership = Depends(require_owner),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, (project_id, user_id))
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a member")
    if membership.role == Role.owner:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Owners can't be removed")
    db.delete(membership)
    ev = record(
        db,
        project_id=project_id,
        actor_id=owner.user_id,
        kind="member_removed",
        data={"user_id": user_id},
    )
    db.commit()
    publish_activity(ev)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
