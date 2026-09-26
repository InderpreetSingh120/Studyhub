"""Group, membership and invite-code endpoints."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .models import Group, GroupMember, User
from .schemas import GroupIn, GroupMemberOut, GroupOut, GroupUpdate, JoinRequest

groups_router = APIRouter(prefix="/groups", tags=["groups"])


INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


def _member_access(
    group_id: int, user: User, db: Session, require_owner: bool = False
) -> tuple[Group, GroupMember]:
    """Load a group the user belongs to.

    Non-members get `404` (a group's existence is not disclosed), members get
    `403` when the endpoint is restricted to the owner.
    """
    row = db.execute(
        select(Group, GroupMember)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(Group.id == group_id, GroupMember.user_id == user.id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Group not found")
    group, membership = row
    if require_owner and membership.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the group owner can do that"
        )
    return group, membership


def _count_members(db: Session, group_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(GroupMember)
            .where(GroupMember.group_id == group_id)
        )
        or 0
    )


def _member_counts(db: Session, group_ids: list[int]) -> dict[int, int]:
    if not group_ids:
        return {}
    return dict(
        db.execute(
            select(GroupMember.group_id, func.count())
            .where(GroupMember.group_id.in_(group_ids))
            .group_by(GroupMember.group_id)
        ).all()
    )


def _group_out(group: Group, role: str, member_count: int) -> GroupOut:
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        invite_code=group.invite_code,
        created_at=group.created_at,
        member_count=member_count,
        my_role=role,
    )


def _new_invite_code(db: Session) -> str:
    """Random, human-friendly code; the alphabet drops look-alike characters."""
    while True:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        if not db.scalar(select(Group.id).where(Group.invite_code == code)):
            return code


@groups_router.get("", response_model=list[GroupOut], summary="List my groups")
def list_groups(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[GroupOut]:
    rows = db.execute(
        select(Group, GroupMember.role)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == current_user.id)
        .order_by(func.lower(Group.name))
    ).all()
    counts = _member_counts(db, [group.id for group, _ in rows])
    return [
        _group_out(group, role, counts.get(group.id, 0)) for group, role in rows
    ]


@groups_router.post("", response_model=GroupOut, status_code=201, summary="Create group")
def create_group(
    payload: GroupIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = Group(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        invite_code=_new_invite_code(db),
    )
    group.members.append(GroupMember(user_id=current_user.id, role="owner"))
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_out(group, "owner", 1)


@groups_router.post("/join", response_model=GroupOut, summary="Join with an invite code")
def join_group(
    payload: JoinRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = db.scalar(select(Group).where(Group.invite_code == payload.invite_code))
    if group is None:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    already_member = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == current_user.id,
        )
    )
    if already_member:
        raise HTTPException(status_code=409, detail="You are already in this group")

    db.add(GroupMember(group_id=group.id, user_id=current_user.id, role="member"))
    db.commit()
    return _group_out(group, "member", _count_members(db, group.id))


@groups_router.get("/{group_id}", response_model=GroupOut, summary="Read group")
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group, membership = _member_access(group_id, current_user, db)
    return _group_out(group, membership.role, _count_members(db, group.id))


@groups_router.get(
    "/{group_id}/members", response_model=list[GroupMemberOut], summary="List members"
)
def list_group_members(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GroupMemberOut]:
    _member_access(group_id, current_user, db)
    rows = db.execute(
        select(GroupMember, User.username)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.user_id)
    ).all()
    return [
        GroupMemberOut(
            user_id=member.user_id,
            username=username,
            role=member.role,
            joined_at=member.joined_at,
        )
        for member, username in rows
    ]


@groups_router.patch("/{group_id}", response_model=GroupOut, summary="Update group")
def update_group(
    group_id: int,
    payload: GroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group, membership = _member_access(group_id, current_user, db, require_owner=True)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return _group_out(group, membership.role, _count_members(db, group.id))


@groups_router.post("/{group_id}/leave", status_code=204, summary="Leave group")
def leave_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    group, membership = _member_access(group_id, current_user, db)

    if membership.role == "owner":
        successors = list(
            db.scalars(
                select(GroupMember)
                .where(
                    GroupMember.group_id == group.id,
                    GroupMember.user_id != current_user.id,
                )
                .order_by(GroupMember.joined_at, GroupMember.user_id)
            )
        )
        if not successors:
            db.delete(group)  # nobody is left to keep the group alive
            db.commit()
            return
        successors[0].role = "owner"
        group.owner_id = successors[0].user_id

    db.delete(membership)
    db.commit()


@groups_router.delete("/{group_id}", status_code=204, summary="Delete group")
def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    group, _ = _member_access(group_id, current_user, db, require_owner=True)
    db.delete(group)
    db.commit()
