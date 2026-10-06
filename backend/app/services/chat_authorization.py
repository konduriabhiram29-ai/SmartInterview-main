"""
SmartInterview — Chat Authorization Service

All permission checks are centralised here.
No router or WebSocket handler should implement auth logic directly.

Principle:
    Authenticated User → Group Membership → Role → Permission

MEMBER can:  read/send messages, leave, access/attempt shared interviews, view published results
ADMIN  can:  all MEMBER actions + manage members/admins, share interviews, view all results, publish results
"""

import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.chat import ChatGroup, ChatGroupMember, MemberRole

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Membership Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_active_membership(
    db: Session,
    user_id: int,
    group_id: int,
) -> ChatGroupMember | None:
    """Return the active membership record or None."""
    return (
        db.query(ChatGroupMember)
        .filter(
            ChatGroupMember.group_id == group_id,
            ChatGroupMember.user_id == user_id,
            ChatGroupMember.is_active == True,
        )
        .first()
    )


def require_membership(
    db: Session,
    user_id: int,
    group_id: int,
) -> ChatGroupMember:
    """Raise 403 if user is not an active member of the group."""
    membership = get_active_membership(db, user_id, group_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group.",
        )
    return membership


def require_admin(
    db: Session,
    user_id: int,
    group_id: int,
) -> ChatGroupMember:
    """Raise 403 if user is not an active ADMIN of the group."""
    membership = get_active_membership(db, user_id, group_id)
    if not membership or membership.role != MemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for this action.",
        )
    return membership


def require_group_exists(db: Session, group_id: int) -> ChatGroup:
    """Raise 404 if group does not exist or is inactive."""
    group = db.query(ChatGroup).filter(
        ChatGroup.id == group_id,
        ChatGroup.is_active == True,
    ).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )
    return group


# ─────────────────────────────────────────────────────────────────────────────
# Admin Safety Rules
# ─────────────────────────────────────────────────────────────────────────────

def count_active_admins(db: Session, group_id: int) -> int:
    """Return the number of active admins in a group."""
    return (
        db.query(ChatGroupMember)
        .filter(
            ChatGroupMember.group_id == group_id,
            ChatGroupMember.role == MemberRole.ADMIN,
            ChatGroupMember.is_active == True,
        )
        .count()
    )


def ensure_not_last_admin(db: Session, group_id: int, user_id: int) -> None:
    """
    Raise 400 if the user is the only active admin in the group.
    Called before demotion or removal of an admin.
    """
    membership = get_active_membership(db, user_id, group_id)
    if membership and membership.role == MemberRole.ADMIN:
        if count_active_admins(db, group_id) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove or demote the last admin. Promote another member first.",
            )


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Auth (no HTTP context — returns None/bool instead of raising)
# ─────────────────────────────────────────────────────────────────────────────

def ws_get_membership(
    db: Session,
    user_id: int,
    group_id: int,
) -> ChatGroupMember | None:
    """Used in WebSocket handlers where we cannot raise HTTPException."""
    return get_active_membership(db, user_id, group_id)


def ws_is_admin(membership: ChatGroupMember | None) -> bool:
    return membership is not None and membership.role == MemberRole.ADMIN


def ws_is_member(membership: ChatGroupMember | None) -> bool:
    return membership is not None and membership.is_active
