"""
SmartInterview — Chat Service (Business Logic)

Handles:
    - Group CRUD
    - Membership management
    - Message persistence
    - Interview sharing
    - Result access and publishing
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from fastapi import HTTPException, status

from app.models.user import User
from app.models.interview import InterviewSession
from app.models.question import AnswerEvaluation, Answer
from app.models.chat import (
    ChatGroup, ChatGroupMember, ChatMessage,
    GroupInterviewShare, GroupInterviewAttempt,
    MemberRole, MessageType, AttemptStatus,
)
from app.services.chat_authorization import (
    require_group_exists, require_membership, require_admin,
    ensure_not_last_admin, count_active_admins, get_active_membership,
)
from app.schemas.chat import (
    CreateGroupRequest, UpdateGroupRequest,
    GroupResponse, GroupDetailResponse, MemberResponse, MessageResponse,
    CandidateResult, InterviewResultsResponse,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _message_to_response(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "group_id": msg.group_id,
        "sender_id": msg.sender_id,
        "sender_name": msg.sender.name if msg.sender else None,
        "sender_email": msg.sender.email if msg.sender else None,
        "message_type": msg.message_type.value if hasattr(msg.message_type, "value") else msg.message_type,
        "content": msg.content,
        "reply_to_message_id": msg.reply_to_message_id,
        "client_message_id": msg.client_message_id,
        "created_at": msg.created_at.isoformat(),
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "deleted_at": msg.deleted_at.isoformat() if msg.deleted_at else None,
        "status": "sent",
    }


def _get_unread_count(db: Session, membership: ChatGroupMember) -> int:
    """Count messages newer than last_read_message_id."""
    if membership.last_read_message_id is None:
        return db.query(ChatMessage).filter(
            ChatMessage.group_id == membership.group_id,
            ChatMessage.deleted_at == None,
        ).count()
    last_msg = db.query(ChatMessage).filter(
        ChatMessage.id == membership.last_read_message_id
    ).first()
    if not last_msg:
        return 0
    return db.query(ChatMessage).filter(
        ChatMessage.group_id == membership.group_id,
        ChatMessage.created_at > last_msg.created_at,
        ChatMessage.deleted_at == None,
    ).count()


# ─────────────────────────────────────────────────────────────────────────────
# Group Management
# ─────────────────────────────────────────────────────────────────────────────

def create_group(db: Session, creator_id: int, req: CreateGroupRequest) -> ChatGroup:
    """Create a group. Creator automatically becomes ADMIN."""
    group = ChatGroup(
        name=req.name,
        description=req.description,
        created_by=creator_id,
    )
    db.add(group)
    db.flush()  # get group.id

    # Creator as ADMIN
    creator_membership = ChatGroupMember(
        group_id=group.id,
        user_id=creator_id,
        role=MemberRole.ADMIN,
    )
    db.add(creator_membership)

    # Additional members
    added = {creator_id}
    for uid in req.member_ids:
        if uid in added:
            continue
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            continue
        db.add(ChatGroupMember(
            group_id=group.id,
            user_id=uid,
            role=MemberRole.MEMBER,
        ))
        added.add(uid)

    # System message
    system_msg = ChatMessage(
        group_id=group.id,
        sender_id=None,
        message_type=MessageType.SYSTEM,
        content={"text": f"Group '{group.name}' was created."},
    )
    db.add(system_msg)
    db.commit()
    db.refresh(group)
    return group


def get_user_groups(db: Session, user_id: int, online_ids: set = None) -> list[dict]:
    """Return all active groups the user belongs to, with unread counts."""
    memberships = (
        db.query(ChatGroupMember)
        .filter(
            ChatGroupMember.user_id == user_id,
            ChatGroupMember.is_active == True,
        )
        .all()
    )
    result = []
    for m in memberships:
        group = m.group
        if not group or not group.is_active:
            continue
        # Last message
        last_msg = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.group_id == group.id,
                ChatMessage.deleted_at == None,
            )
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        # Member count
        member_count = (
            db.query(ChatGroupMember)
            .filter(
                ChatGroupMember.group_id == group.id,
                ChatGroupMember.is_active == True,
            )
            .count()
        )
        # Online count (approximate)
        member_ids = [
            row.user_id
            for row in db.query(ChatGroupMember.user_id)
            .filter(ChatGroupMember.group_id == group.id, ChatGroupMember.is_active == True)
            .all()
        ]
        online_count = len(online_ids & set(member_ids)) if online_ids else 0

        result.append({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "avatar_url": group.avatar_url,
            "created_by": group.created_by,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "is_active": group.is_active,
            "member_count": member_count,
            "online_count": online_count,
            "unread_count": _get_unread_count(db, m),
            "last_message": _message_to_response(last_msg) if last_msg else None,
        })
    # Sort by last message timestamp descending
    result.sort(
        key=lambda g: g["last_message"]["created_at"] if g["last_message"] else g["created_at"].isoformat(),
        reverse=True,
    )
    return result


def get_group_detail(db: Session, user_id: int, group_id: int) -> dict:
    """Return group detail including members. Validates membership."""
    group = require_group_exists(db, group_id)
    require_membership(db, user_id, group_id)

    members_q = (
        db.query(ChatGroupMember)
        .filter(
            ChatGroupMember.group_id == group_id,
            ChatGroupMember.is_active == True,
        )
        .all()
    )
    members = []
    for m in members_q:
        if m.user:
            members.append({
                "user_id": m.user_id,
                "name": m.user.name,
                "email": m.user.email,
                "role": m.role.value if hasattr(m.role, "value") else m.role,
                "joined_at": m.joined_at,
                "is_active": m.is_active,
            })

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "avatar_url": group.avatar_url,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
        "is_active": group.is_active,
        "member_count": len(members),
        "online_count": 0,
        "unread_count": 0,
        "last_message": None,
        "members": members,
    }


def update_group(db: Session, user_id: int, group_id: int, req: UpdateGroupRequest) -> ChatGroup:
    group = require_group_exists(db, group_id)
    require_admin(db, user_id, group_id)
    if req.name is not None:
        group.name = req.name
    if req.description is not None:
        group.description = req.description
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, user_id: int, group_id: int) -> None:
    group = require_group_exists(db, group_id)
    require_admin(db, user_id, group_id)
    group.is_active = False
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Membership Management
# ─────────────────────────────────────────────────────────────────────────────

def add_members(db: Session, requester_id: int, group_id: int, user_ids: list[int]) -> list[dict]:
    require_group_exists(db, group_id)
    require_admin(db, requester_id, group_id)
    added = []
    for uid in user_ids:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            continue
        existing = db.query(ChatGroupMember).filter(
            ChatGroupMember.group_id == group_id,
            ChatGroupMember.user_id == uid,
        ).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.left_at = None
                existing.role = MemberRole.MEMBER
                db.flush()
                added.append(uid)
        else:
            db.add(ChatGroupMember(group_id=group_id, user_id=uid, role=MemberRole.MEMBER))
            db.flush()
            added.append(uid)

    if added:
        # System message
        db.add(ChatMessage(
            group_id=group_id,
            sender_id=None,
            message_type=MessageType.SYSTEM,
            content={"text": f"{len(added)} member(s) added to the group."},
        ))
        db.commit()
    return added


def remove_member(db: Session, requester_id: int, group_id: int, target_user_id: int) -> None:
    require_group_exists(db, group_id)
    require_admin(db, requester_id, group_id)

    # Prevent removing last admin
    ensure_not_last_admin(db, group_id, target_user_id)

    membership = get_active_membership(db, target_user_id, group_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found in group.")
    membership.is_active = False
    membership.left_at = datetime.now(timezone.utc)

    target_user = db.query(User).filter(User.id == target_user_id).first()
    db.add(ChatMessage(
        group_id=group_id,
        sender_id=None,
        message_type=MessageType.SYSTEM,
        content={"text": f"{target_user.name if target_user else 'A member'} was removed from the group."},
    ))
    db.commit()


def leave_group(db: Session, user_id: int, group_id: int) -> None:
    require_group_exists(db, group_id)
    membership = require_membership(db, user_id, group_id)
    ensure_not_last_admin(db, group_id, user_id)
    membership.is_active = False
    membership.left_at = datetime.now(timezone.utc)
    user = db.query(User).filter(User.id == user_id).first()
    db.add(ChatMessage(
        group_id=group_id,
        sender_id=None,
        message_type=MessageType.SYSTEM,
        content={"text": f"{user.name if user else 'A member'} left the group."},
    ))
    db.commit()


def promote_to_admin(db: Session, requester_id: int, group_id: int, target_user_id: int) -> None:
    require_group_exists(db, group_id)
    require_admin(db, requester_id, group_id)
    membership = get_active_membership(db, target_user_id, group_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found.")
    membership.role = MemberRole.ADMIN
    db.commit()


def demote_from_admin(db: Session, requester_id: int, group_id: int, target_user_id: int) -> None:
    require_group_exists(db, group_id)
    require_admin(db, requester_id, group_id)
    ensure_not_last_admin(db, group_id, target_user_id)
    membership = get_active_membership(db, target_user_id, group_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found.")
    membership.role = MemberRole.MEMBER
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Message Persistence
# ─────────────────────────────────────────────────────────────────────────────

def persist_text_message(
    db: Session,
    user_id: int,
    group_id: int,
    content_text: str,
    client_message_id: Optional[str] = None,
    reply_to_id: Optional[int] = None,
) -> ChatMessage:
    """
    Persist a TEXT message with idempotency via client_message_id.
    If duplicate, return existing message (idempotent).
    """
    require_group_exists(db, group_id)
    require_membership(db, user_id, group_id)

    # Idempotency check
    if client_message_id:
        existing = db.query(ChatMessage).filter(
            ChatMessage.sender_id == user_id,
            ChatMessage.client_message_id == client_message_id,
        ).first()
        if existing:
            return existing

    msg = ChatMessage(
        group_id=group_id,
        sender_id=user_id,
        message_type=MessageType.TEXT,
        content={"text": content_text},
        reply_to_message_id=reply_to_id,
        client_message_id=client_message_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # Eager load sender
    db.refresh(msg)
    return msg


def get_messages(
    db: Session,
    user_id: int,
    group_id: int,
    limit: int = 50,
    before_id: Optional[int] = None,
) -> dict:
    """
    Cursor-based paginated message history.
    Returns messages in ascending order (oldest first) so UI renders top→bottom.
    """
    require_group_exists(db, group_id)
    require_membership(db, user_id, group_id)

    query = db.query(ChatMessage).filter(
        ChatMessage.group_id == group_id,
        ChatMessage.deleted_at == None,
    )
    if before_id:
        query = query.filter(ChatMessage.id < before_id)

    total_in_window = query.count()
    messages = (
        query
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    messages = list(reversed(messages))  # ascending for UI rendering

    has_more = total_in_window > limit
    next_cursor = messages[0].id if messages and has_more else None

    return {
        "messages": [_message_to_response(m) for m in messages],
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


def mark_read(db: Session, user_id: int, group_id: int, message_id: int) -> None:
    """Update last_read_message_id for the user's membership."""
    membership = require_membership(db, user_id, group_id)
    if (
        membership.last_read_message_id is None
        or membership.last_read_message_id < message_id
    ):
        membership.last_read_message_id = message_id
        db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Interview Sharing
# ─────────────────────────────────────────────────────────────────────────────

def share_interview(
    db: Session,
    admin_id: int,
    group_id: int,
    interview_session_id: int,
) -> tuple[GroupInterviewShare, ChatMessage]:
    """Admin shares an interview session into the group."""
    require_group_exists(db, group_id)
    require_admin(db, admin_id, group_id)

    # Verify the session exists and belongs to the admin
    session = db.query(InterviewSession).filter(
        InterviewSession.id == interview_session_id,
        InterviewSession.user_id == admin_id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found or you don't have permission to share it.",
        )

    # Build a descriptive content payload
    skill_label = ", ".join(session.selected_skills or []) if session.selected_skills else "General"
    content = {
        "share_id": None,  # filled after flush
        "session_id": interview_session_id,
        "title": f"{skill_label} Interview",
        "difficulty": session.difficulty,
        "question_count": session.question_count,
        "status": session.status,
    }
    msg = ChatMessage(
        group_id=group_id,
        sender_id=admin_id,
        message_type=MessageType.INTERVIEW,
        content=content,
    )
    db.add(msg)
    db.flush()

    share = GroupInterviewShare(
        group_id=group_id,
        interview_session_id=interview_session_id,
        posted_by=admin_id,
        message_id=msg.id,
    )
    db.add(share)
    db.flush()

    # Patch content with share_id now that it's known
    msg.content = {**msg.content, "share_id": share.id}
    db.commit()
    db.refresh(share)
    db.refresh(msg)
    return share, msg


def create_or_get_attempt(
    db: Session,
    user_id: int,
    group_id: int,
    share_id: int,
) -> GroupInterviewAttempt:
    """
    Create or return an existing GroupInterviewAttempt.
    The actual interview session is created separately by the existing interview API.
    """
    require_group_exists(db, group_id)
    require_membership(db, user_id, group_id)

    share = db.query(GroupInterviewShare).filter(
        GroupInterviewShare.id == share_id,
        GroupInterviewShare.group_id == group_id,
        GroupInterviewShare.is_active == True,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Interview share not found.")

    existing = db.query(GroupInterviewAttempt).filter(
        GroupInterviewAttempt.share_id == share_id,
        GroupInterviewAttempt.user_id == user_id,
    ).first()
    if existing:
        return existing

    attempt = GroupInterviewAttempt(
        share_id=share_id,
        user_id=user_id,
        status=AttemptStatus.NOT_STARTED,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def link_attempt_to_session(
    db: Session,
    attempt_id: int,
    interview_session_id: int,
) -> GroupInterviewAttempt:
    """Link an attempt to the actual interview session that was created."""
    attempt = db.query(GroupInterviewAttempt).filter(GroupInterviewAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    attempt.interview_session_id = interview_session_id
    attempt.status = AttemptStatus.IN_PROGRESS
    db.commit()
    db.refresh(attempt)
    return attempt


def update_attempt_status(db: Session, interview_session_id: int) -> None:
    """Called after an interview completes — mark attempt as COMPLETED."""
    attempt = db.query(GroupInterviewAttempt).filter(
        GroupInterviewAttempt.interview_session_id == interview_session_id,
    ).first()
    if attempt:
        attempt.status = AttemptStatus.COMPLETED
        db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────

def get_share_results(
    db: Session,
    admin_id: int,
    group_id: int,
    share_id: int,
) -> dict:
    """Return all candidate results for a shared interview (admin only)."""
    require_group_exists(db, group_id)
    require_admin(db, admin_id, group_id)

    share = db.query(GroupInterviewShare).filter(
        GroupInterviewShare.id == share_id,
        GroupInterviewShare.group_id == group_id,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Interview share not found.")

    session = share.interview_session
    skill_label = ", ".join(session.selected_skills or []) if session.selected_skills else "General"

    # Get all group members
    members = (
        db.query(ChatGroupMember)
        .filter(
            ChatGroupMember.group_id == group_id,
            ChatGroupMember.is_active == True,
        )
        .all()
    )

    candidates = []
    for m in members:
        user = m.user
        attempt = db.query(GroupInterviewAttempt).filter(
            GroupInterviewAttempt.share_id == share_id,
            GroupInterviewAttempt.user_id == m.user_id,
        ).first()

        result: CandidateResult = {
            "user_id": m.user_id,
            "name": user.name if user else "Unknown",
            "email": user.email if user else "",
            "status": attempt.status.value if attempt else AttemptStatus.NOT_STARTED.value,
            "attempt_id": attempt.id if attempt else None,
            "interview_session_id": attempt.interview_session_id if attempt else None,
            "overall_score": None,
            "technical_score": None,
            "completeness_score": None,
            "relevance_score": None,
        }

        if attempt and attempt.interview_session_id:
            # Compute average scores from AnswerEvaluation
            evals = (
                db.query(AnswerEvaluation)
                .join(Answer, AnswerEvaluation.answer_id == Answer.id)
                .filter(Answer.session_id == attempt.interview_session_id)
                .all()
            )
            if evals:
                result["overall_score"] = round(sum(e.overall_score for e in evals) / len(evals), 1)
                result["technical_score"] = round(sum(e.technical_score for e in evals) / len(evals), 1)
                result["completeness_score"] = round(sum(e.completeness_score for e in evals) / len(evals), 1)
                result["relevance_score"] = round(sum(e.relevance_score for e in evals) / len(evals), 1)

        candidates.append(result)

    return {
        "share_id": share_id,
        "interview_session_id": share.interview_session_id,
        "session_title": f"{skill_label} Interview",
        "candidates": candidates,
    }


def publish_result(
    db: Session,
    admin_id: int,
    group_id: int,
    share_id: int,
    candidate_user_id: int,
) -> ChatMessage:
    """Admin publishes a candidate's score as an INTERVIEW_RESULT message."""
    require_group_exists(db, group_id)
    require_admin(db, admin_id, group_id)

    share = db.query(GroupInterviewShare).filter(
        GroupInterviewShare.id == share_id,
        GroupInterviewShare.group_id == group_id,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Interview share not found.")

    attempt = db.query(GroupInterviewAttempt).filter(
        GroupInterviewAttempt.share_id == share_id,
        GroupInterviewAttempt.user_id == candidate_user_id,
    ).first()
    if not attempt or attempt.status != AttemptStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Candidate has not completed this interview.")

    candidate = db.query(User).filter(User.id == candidate_user_id).first()
    session = share.interview_session
    skill_label = ", ".join(session.selected_skills or []) if session.selected_skills else "General"

    evals = (
        db.query(AnswerEvaluation)
        .join(Answer, AnswerEvaluation.answer_id == Answer.id)
        .filter(Answer.session_id == attempt.interview_session_id)
        .all()
    )
    overall_score = round(sum(e.overall_score for e in evals) / len(evals), 1) if evals else 0
    technical_score = round(sum(e.technical_score for e in evals) / len(evals), 1) if evals else 0
    completeness_score = round(sum(e.completeness_score for e in evals) / len(evals), 1) if evals else 0
    relevance_score = round(sum(e.relevance_score for e in evals) / len(evals), 1) if evals else 0

    content = {
        "share_id": share_id,
        "session_id": share.interview_session_id,
        "candidate_user_id": candidate_user_id,
        "candidate_name": candidate.name if candidate else "Unknown",
        "session_title": f"{skill_label} Interview",
        "overall_score": overall_score,
        "technical_score": technical_score,
        "completeness_score": completeness_score,
        "relevance_score": relevance_score,
        "interview_session_id_for_candidate": attempt.interview_session_id,
    }

    msg = ChatMessage(
        group_id=group_id,
        sender_id=admin_id,
        message_type=MessageType.INTERVIEW_RESULT,
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# User Search
# ─────────────────────────────────────────────────────────────────────────────

def search_users(db: Session, query: str, limit: int = 20) -> list[dict]:
    """Search users by name or email for adding to groups."""
    q = f"%{query}%"
    users = (
        db.query(User)
        .filter(
            (User.name.ilike(q)) | (User.email.ilike(q))
        )
        .limit(limit)
        .all()
    )
    return [{"id": u.id, "name": u.name, "email": u.email} for u in users]
