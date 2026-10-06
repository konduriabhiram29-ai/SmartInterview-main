"""
SmartInterview — Chat Pydantic Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Shared
# ─────────────────────────────────────────────────────────────────────────────

class UserBrief(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Group
# ─────────────────────────────────────────────────────────────────────────────

class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    member_ids: List[int] = Field(default_factory=list)


class UpdateGroupRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)


class MemberResponse(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    joined_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    avatar_url: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    member_count: int = 0
    online_count: int = 0
    unread_count: int = 0
    last_message: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class GroupDetailResponse(GroupResponse):
    members: List[MemberResponse] = []


# ─────────────────────────────────────────────────────────────────────────────
# Members
# ─────────────────────────────────────────────────────────────────────────────

class AddMembersRequest(BaseModel):
    user_ids: List[int] = Field(..., min_length=1)


class UserSearchResult(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: int
    group_id: int
    sender_id: Optional[int]
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    message_type: str
    content: Dict[str, Any]
    reply_to_message_id: Optional[int] = None
    client_message_id: Optional[str] = None
    created_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    status: str = "sent"  # optimistic UI support

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    has_more: bool
    next_cursor: Optional[int] = None  # message id for cursor-based pagination


class MarkReadRequest(BaseModel):
    message_id: int


# ─────────────────────────────────────────────────────────────────────────────
# Interview Share
# ─────────────────────────────────────────────────────────────────────────────

class ShareInterviewRequest(BaseModel):
    interview_session_id: int


class InterviewShareResponse(BaseModel):
    id: int
    group_id: int
    interview_session_id: int
    posted_by: Optional[int]
    message_id: Optional[int]
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Interview Attempt
# ─────────────────────────────────────────────────────────────────────────────

class AttemptInterviewRequest(BaseModel):
    share_id: int


class AttemptResponse(BaseModel):
    attempt_id: int
    share_id: int
    user_id: int
    interview_session_id: Optional[int]
    status: str
    attempted_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────

class CandidateResult(BaseModel):
    user_id: int
    name: str
    email: str
    status: str                          # NOT_STARTED | IN_PROGRESS | COMPLETED
    attempt_id: Optional[int] = None
    interview_session_id: Optional[int] = None
    overall_score: Optional[float] = None
    technical_score: Optional[float] = None
    completeness_score: Optional[float] = None
    relevance_score: Optional[float] = None


class InterviewResultsResponse(BaseModel):
    share_id: int
    interview_session_id: int
    session_title: str
    candidates: List[CandidateResult]


class PublishResultRequest(BaseModel):
    share_id: int
    user_id: int   # candidate whose result to publish


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Events (centralized event type constants + schemas)
# ─────────────────────────────────────────────────────────────────────────────

class WSEventType:
    # Client → Server
    MESSAGE_SEND        = "message.send"
    TYPING_START        = "typing.start"
    TYPING_STOP         = "typing.stop"
    PING                = "ping"
    PRESENCE_HEARTBEAT  = "presence.heartbeat"

    # Server → Client
    MESSAGE_ACK         = "message.ack"
    MESSAGE_NEW         = "message.new"
    TYPING              = "typing"
    PRESENCE            = "presence"
    PONG                = "pong"
    ERROR               = "error"
    INTERVIEW_SHARED    = "interview.shared"
    RESULT_PUBLISHED    = "interview.result_published"
    MEMBER_JOINED       = "member.joined"
    MEMBER_LEFT         = "member.left"


class WSErrorCode:
    NOT_MEMBER          = "NOT_GROUP_MEMBER"
    NOT_ADMIN           = "NOT_ADMIN"
    UNAUTHORIZED        = "UNAUTHORIZED"
    RATE_LIMITED        = "RATE_LIMITED"
    INVALID_PAYLOAD     = "INVALID_PAYLOAD"
    GROUP_NOT_FOUND     = "GROUP_NOT_FOUND"
    DUPLICATE_MESSAGE   = "DUPLICATE_MESSAGE"
    SERVER_ERROR        = "SERVER_ERROR"
