"""
SmartInterview — Chat Domain Models

Tables:
    chat_groups              — group entity
    chat_group_members       — membership + role (ADMIN | MEMBER)
    chat_messages            — all messages (TEXT | SYSTEM | INTERVIEW | INTERVIEW_RESULT)
    group_interview_shares   — interview session posted to a group
    group_interview_attempts — tracks who attempted a shared interview
"""

import enum
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Enum as SAEnum,
    ForeignKey, JSON, UniqueConstraint, Index, func,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ── Enum Types ─────────────────────────────────────────────────────────────

class MemberRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class MessageType(str, enum.Enum):
    TEXT = "TEXT"
    SYSTEM = "SYSTEM"
    INTERVIEW = "INTERVIEW"
    INTERVIEW_RESULT = "INTERVIEW_RESULT"


class AttemptStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


# ── ChatGroup ──────────────────────────────────────────────────────────────

class ChatGroup(Base):
    __tablename__ = "chat_groups"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    avatar_url  = Column(String(500), nullable=True)
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    is_active   = Column(Boolean, default=True, nullable=False)

    # Relationships
    creator  = relationship("User", foreign_keys=[created_by], backref="created_chat_groups")
    members  = relationship("ChatGroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="group", cascade="all, delete-orphan")
    interview_shares = relationship("GroupInterviewShare", back_populates="group", cascade="all, delete-orphan")


# ── ChatGroupMember ────────────────────────────────────────────────────────

class ChatGroupMember(Base):
    __tablename__ = "chat_group_members"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    group_id    = Column(Integer, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role        = Column(SAEnum(MemberRole), default=MemberRole.MEMBER, nullable=False)
    joined_at   = Column(DateTime, server_default=func.now(), nullable=False)
    left_at     = Column(DateTime, nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False)
    # Cursor for unread message counting
    last_read_message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    group = relationship("ChatGroup", back_populates="members")
    user  = relationship("User", foreign_keys=[user_id], backref="chat_memberships")
    last_read_message = relationship(
        "ChatMessage",
        foreign_keys=[last_read_message_id],
        primaryjoin="ChatGroupMember.last_read_message_id == ChatMessage.id",
        uselist=False,
    )

    __table_args__ = (
        # A user can only be an active member of a group once
        UniqueConstraint("group_id", "user_id", name="uq_chat_group_member"),
        # Queries: all members of a group
        Index("idx_cgm_group_user", "group_id", "user_id"),
        # Queries: all groups a user belongs to
        Index("idx_cgm_user_group", "user_id", "group_id"),
    )


# ── ChatMessage ────────────────────────────────────────────────────────────

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    group_id          = Column(Integer, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False)
    sender_id         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_type      = Column(SAEnum(MessageType), default=MessageType.TEXT, nullable=False)
    # content is stored as JSON so future message types can carry structured payloads
    # For TEXT: {"text": "..."}
    # For INTERVIEW: {"share_id": 99, "session_id": 5, "title": "...", ...}
    # For INTERVIEW_RESULT: {"share_id": 99, "user_id": 10, "score": 82, ...}
    # For SYSTEM: {"text": "User joined the group"}
    content           = Column(JSON, nullable=False, default=dict)
    reply_to_message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    created_at        = Column(DateTime, server_default=func.now(), nullable=False)
    edited_at         = Column(DateTime, nullable=True)
    deleted_at        = Column(DateTime, nullable=True)
    # Idempotency key: sender_id + client_message_id must be unique
    client_message_id = Column(String(100), nullable=True)

    # Relationships
    group      = relationship("ChatGroup", back_populates="messages")
    sender     = relationship("User", foreign_keys=[sender_id], backref="chat_messages_sent")
    reply_to   = relationship("ChatMessage", remote_side=[id], foreign_keys=[reply_to_message_id])

    __table_args__ = (
        # Idempotency: prevent duplicate client retries
        UniqueConstraint("sender_id", "client_message_id", name="uq_msg_sender_client_id"),
        # Core query: paginate messages in a group (cursor-based)
        Index("idx_cm_group_created", "group_id", "created_at"),
        # Core query: cursor pagination by id
        Index("idx_cm_group_id", "group_id", "id"),
        # Query: messages by sender
        Index("idx_cm_sender_created", "sender_id", "created_at"),
    )


# ── GroupInterviewShare ────────────────────────────────────────────────────

class GroupInterviewShare(Base):
    """An interview session posted (shared) into a group by an admin."""
    __tablename__ = "group_interview_shares"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    group_id            = Column(Integer, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False)
    interview_session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    posted_by           = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # FK to the chat message that contains this share card
    message_id          = Column(Integer, ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    created_at          = Column(DateTime, server_default=func.now(), nullable=False)
    is_active           = Column(Boolean, default=True, nullable=False)

    # Relationships
    group            = relationship("ChatGroup", back_populates="interview_shares")
    interview_session = relationship("InterviewSession", foreign_keys=[interview_session_id])
    poster           = relationship("User", foreign_keys=[posted_by])
    message          = relationship("ChatMessage", foreign_keys=[message_id])
    attempts         = relationship("GroupInterviewAttempt", back_populates="share", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_gis_group_created", "group_id", "created_at"),
    )


# ── GroupInterviewAttempt ─────────────────────────────────────────────────

class GroupInterviewAttempt(Base):
    """
    Tracks which group member attempted a shared interview.
    The actual interview session (questions, answers, scores) lives in
    InterviewSession / AnswerEvaluation — we simply reference it here.
    """
    __tablename__ = "group_interview_attempts"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    share_id             = Column(Integer, ForeignKey("group_interview_shares.id", ondelete="CASCADE"), nullable=False)
    user_id              = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # The new session created for this attempt
    interview_session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="SET NULL"), nullable=True)
    status               = Column(SAEnum(AttemptStatus), default=AttemptStatus.NOT_STARTED, nullable=False)
    attempted_at         = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    share            = relationship("GroupInterviewShare", back_populates="attempts")
    user             = relationship("User", foreign_keys=[user_id])
    interview_session = relationship("InterviewSession", foreign_keys=[interview_session_id])

    __table_args__ = (
        # A user can only have one attempt per share
        UniqueConstraint("share_id", "user_id", name="uq_gia_share_user"),
        Index("idx_gia_share", "share_id"),
        Index("idx_gia_user", "user_id"),
    )
