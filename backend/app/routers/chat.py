"""
SmartInterview — Chat REST Router

Endpoints:
    POST   /api/chat/groups                                     Create group
    GET    /api/chat/groups                                     List my groups
    GET    /api/chat/groups/{group_id}                          Group detail
    PATCH  /api/chat/groups/{group_id}                          Update group info
    DELETE /api/chat/groups/{group_id}                          Deactivate group
    GET    /api/chat/groups/{group_id}/messages                 Message history
    POST   /api/chat/groups/{group_id}/read                     Mark read
    POST   /api/chat/groups/{group_id}/members                  Add members
    DELETE /api/chat/groups/{group_id}/members/{user_id}        Remove member
    POST   /api/chat/groups/{group_id}/admins/{user_id}         Promote to admin
    DELETE /api/chat/groups/{group_id}/admins/{user_id}         Demote admin
    GET    /api/chat/users/search                               Search users
    POST   /api/chat/groups/{group_id}/interviews               Share interview
    POST   /api/chat/groups/{group_id}/interviews/{share_id}/attempt  Begin attempt
    POST   /api/chat/groups/{group_id}/interviews/{share_id}/attempt/{attempt_id}/link  Link session
    GET    /api/chat/groups/{group_id}/interviews/{share_id}/results  Admin results
    POST   /api/chat/groups/{group_id}/interviews/{share_id}/publish/{user_id}  Publish result
    
WebSocket:
    WS    /ws/chat?token=<JWT>                                   Real-time chat
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.chat import (
    CreateGroupRequest, UpdateGroupRequest, AddMembersRequest,
    ShareInterviewRequest, MarkReadRequest, AttemptInterviewRequest,
    PublishResultRequest,
)
from app.services import chat_service, redis_service
from app.services.chat_websocket import handle_chat_websocket, manager, generate_ws_ticket
from app.services.chat_service import (
    create_group, get_user_groups, get_group_detail, update_group, delete_group,
    add_members, remove_member, leave_group, promote_to_admin, demote_from_admin,
    get_messages, mark_read, share_interview, create_or_get_attempt,
    link_attempt_to_session, get_share_results, publish_result, search_users,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])
ws_router = APIRouter(tags=["chat-ws"])


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket & Ticket Authentication
# ─────────────────────────────────────────────────────────────────────────────

@ws_router.websocket("/ws/chat")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    ticket: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time chat.
    Authentication: pass short-lived ticket ?ticket=<ticket> (recommended)
    or JWT query param ?token=<JWT> (legacy fallback).
    """
    await handle_chat_websocket(websocket, token=token, ticket=ticket)


@router.post("/ws-ticket")
def issue_ws_ticket(
    current_user: User = Depends(get_current_user),
):
    """
    Issue a short-lived (60s), single-use scoped WebSocket ticket.
    Protects long-lived JWTs from being exposed in browser history or proxy URLs.
    """
    ticket = generate_ws_ticket(current_user.id)
    return {"ticket": ticket, "expires_in": 60}


# ─────────────────────────────────────────────────────────────────────────────
# Groups
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group_endpoint(
    req: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Rate limit group creation
    allowed = await redis_service.check_group_create_rate_limit(current_user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many group creation requests. Try again later.")

    group = create_group(db, current_user.id, req)
    # Notify WebSocket connections about new group membership
    for uid in req.member_ids:
        await manager.add_user_to_group(uid, group.id)
    await manager.add_user_to_group(current_user.id, group.id)

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_by": group.created_by,
        "created_at": group.created_at,
    }


@router.get("/groups")
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get online user IDs for online count (best-effort)
    try:
        connected = manager.get_connected_user_ids()
        online_ids = set(connected)
    except Exception:
        online_ids = set()

    groups = get_user_groups(db, current_user.id, online_ids=online_ids)
    return {"groups": groups}


@router.get("/groups/{group_id}")
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_group_detail(db, current_user.id, group_id)


@router.patch("/groups/{group_id}")
def update_group_endpoint(
    group_id: int,
    req: UpdateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = update_group(db, current_user.id, group_id, req)
    return {"id": group.id, "name": group.name, "description": group.description}


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_endpoint(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delete_group(db, current_user.id, group_id)


# ─────────────────────────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/groups/{group_id}/messages")
def get_group_messages(
    group_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    before: Optional[int] = Query(default=None, description="Message ID cursor for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cursor-based paginated message history."""
    return get_messages(db, current_user.id, group_id, limit=limit, before_id=before)


@router.post("/groups/{group_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_messages_read(
    group_id: int,
    req: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update last_read_message_id to reset unread count."""
    mark_read(db, current_user.id, group_id, req.message_id)


# ─────────────────────────────────────────────────────────────────────────────
# Members
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/groups/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_members_endpoint(
    group_id: int,
    req: AddMembersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    added = add_members(db, current_user.id, group_id, req.user_ids)
    # Notify WebSocket connections
    for uid in added:
        await manager.add_user_to_group(uid, group_id)
    # Broadcast member joined event
    for uid in added:
        user = db.query(User).filter(User.id == uid).first()
        await manager.broadcast_to_group(group_id, {
            "type": "member.joined",
            "group_id": group_id,
            "user_id": uid,
            "name": user.name if user else "Unknown",
        })
    return {"added": added}


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_endpoint(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    remove_member(db, current_user.id, group_id, user_id)
    await manager.remove_user_from_group(user_id, group_id)
    await manager.broadcast_to_group(group_id, {
        "type": "member.left",
        "group_id": group_id,
        "user_id": user_id,
    })


@router.delete("/groups/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group_endpoint(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leave_group(db, current_user.id, group_id)
    await manager.remove_user_from_group(current_user.id, group_id)


# ─────────────────────────────────────────────────────────────────────────────
# Admin Management
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/groups/{group_id}/admins/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def promote_admin(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    promote_to_admin(db, current_user.id, group_id, user_id)


@router.delete("/groups/{group_id}/admins/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def demote_admin(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    demote_from_admin(db, current_user.id, group_id, user_id)


# ─────────────────────────────────────────────────────────────────────────────
# User Search
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users/search")
def search_users_endpoint(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = search_users(db, q, limit=limit)
    # Exclude the requester from results
    results = [r for r in results if r["id"] != current_user.id]
    return {"users": results}


# ─────────────────────────────────────────────────────────────────────────────
# Interview Sharing
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/groups/{group_id}/interviews", status_code=status.HTTP_201_CREATED)
async def share_interview_endpoint(
    group_id: int,
    req: ShareInterviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    share, msg = share_interview(db, current_user.id, group_id, req.interview_session_id)
    # Broadcast interview shared event
    await manager.broadcast_to_group(group_id, {
        "type": "interview.shared",
        "group_id": group_id,
        "share_id": share.id,
        "message": {
            "id": msg.id,
            "group_id": msg.group_id,
            "sender_id": msg.sender_id,
            "message_type": "INTERVIEW",
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "status": "sent",
        },
    })
    return {
        "share_id": share.id,
        "group_id": group_id,
        "interview_session_id": share.interview_session_id,
        "message_id": msg.id,
    }


@router.post("/groups/{group_id}/interviews/{share_id}/attempt", status_code=status.HTTP_201_CREATED)
def start_attempt(
    group_id: int,
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create (or return existing) attempt for the user.
    The frontend then calls the existing POST /api/interviews/start to create the actual session,
    and links it back using the /link endpoint below.
    """
    attempt = create_or_get_attempt(db, current_user.id, group_id, share_id)
    share = db.query(chat_service.GroupInterviewShare).filter(
        chat_service.GroupInterviewShare.id == share_id
    ).first()
    return {
        "attempt_id": attempt.id,
        "share_id": share_id,
        "status": attempt.status.value if hasattr(attempt.status, "value") else attempt.status,
        "interview_session_id": attempt.interview_session_id,
        "original_session_id": share.interview_session_id if share else None,
        "original_session": {
            "difficulty": share.interview_session.difficulty if share else None,
            "question_count": share.interview_session.question_count if share else None,
            "selected_skills": share.interview_session.selected_skills if share else None,
            "question_type": share.interview_session.question_type if share else None,
        } if share else None,
    }


@router.post("/groups/{group_id}/interviews/{share_id}/attempt/{attempt_id}/link")
def link_attempt_session(
    group_id: int,
    share_id: int,
    attempt_id: int,
    interview_session_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """After calling /api/interviews/start, link the new session_id to the attempt."""
    attempt = link_attempt_to_session(
        db,
        attempt_id,
        interview_session_id,
        user_id=current_user.id,
        group_id=group_id,
        share_id=share_id,
    )
    return {
        "attempt_id": attempt.id,
        "interview_session_id": attempt.interview_session_id,
        "status": attempt.status.value if hasattr(attempt.status, "value") else attempt.status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/groups/{group_id}/interviews/{share_id}/results")
def get_results(
    group_id: int,
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: get all candidate scores for a shared interview."""
    return get_share_results(db, current_user.id, group_id, share_id)


@router.post("/groups/{group_id}/interviews/{share_id}/publish/{candidate_user_id}")
async def publish_result_endpoint(
    group_id: int,
    share_id: int,
    candidate_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin: publish a candidate's result as a chat message."""
    msg = publish_result(db, current_user.id, group_id, share_id, candidate_user_id)
    result_event = {
        "type": "interview.result_published",
        "group_id": group_id,
        "share_id": share_id,
        "message": {
            "id": msg.id,
            "group_id": msg.group_id,
            "sender_id": msg.sender_id,
            "message_type": "INTERVIEW_RESULT",
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "status": "sent",
        },
    }
    await manager.broadcast_to_group(group_id, result_event)
    return {"message_id": msg.id, "published": True}
