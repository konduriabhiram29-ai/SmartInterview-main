"""
SmartInterview — Security & WebSocket Authorization Unit & Integration Tests

Tests covering:
  1. Scoped WebSocket tickets (generation, verification, expiration, scope isolation).
  2. Multi-device / multi-tab connection management:
     - Independent connection IDs.
     - Preserved user presence until the last connection disconnects.
     - Group broadcast to multiple tabs of the same user.
  3. Typing-event authorization:
     - Active members can broadcast typing events.
     - Non-members are rejected before Redis writes or broadcasts.
     - Malformed payloads are safely rejected.
  4. Attempt linking authorization & isolation:
     - User cannot hijack another candidate's attempt.
     - User cannot link a session belonging to another user.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.services.chat_websocket import (
    generate_ws_ticket,
    decode_ws_ticket,
    decode_ws_token,
    authenticate_ws_credential,
    ChatConnectionManager,
    _handle_typing,
    WS_TICKET_EXPIRATION_SECONDS,
)
from app.schemas.chat import WSEventType, WSErrorCode
from app.models.chat import GroupInterviewAttempt, GroupInterviewShare, AttemptStatus
from app.models.interview import InterviewSession
from app.services.chat_service import link_attempt_to_session
from app.config import JWT_SECRET_KEY, JWT_ALGORITHM
from jose import jwt


# ── 1. WebSocket Ticket Tests ──────────────────────────────────────────

class TestWebSocketTicketAuth:
    def test_valid_ticket_generation_and_decoding(self):
        user_id = 42
        ticket = generate_ws_ticket(user_id)
        assert isinstance(ticket, str)
        decoded_uid = decode_ws_ticket(ticket)
        assert decoded_uid == user_id

    def test_expired_ticket_fails(self):
        user_id = 99
        # Create an already-expired ticket
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "scope": "ws_chat",
            "exp": int((now - timedelta(seconds=10)).timestamp()),
        }
        expired_ticket = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        assert decode_ws_ticket(expired_ticket) is None
        assert authenticate_ws_credential(ticket=expired_ticket) is None

    def test_invalid_scope_fails(self):
        user_id = 123
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "scope": "api_access",  # Not ws_chat
            "exp": int((now + timedelta(seconds=60)).timestamp()),
        }
        bad_scope_ticket = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        assert decode_ws_ticket(bad_scope_ticket) is None

    def test_tampered_ticket_signature_fails(self):
        ticket = generate_ws_ticket(10)
        tampered = ticket[:-4] + "abcd"
        assert decode_ws_ticket(tampered) is None

    def test_authenticate_ws_credential_fallback_to_token(self):
        user_id = 55
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        }
        legacy_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # When ticket is absent, falls back to legacy token
        assert authenticate_ws_credential(token=legacy_token) == user_id
        # When ticket is valid, uses ticket
        ticket = generate_ws_ticket(user_id)
        assert authenticate_ws_credential(ticket=ticket) == user_id


# ── 2. Multi-Device Connection Manager Tests ───────────────────────────

class TestMultiDeviceConnectionManager:
    def test_multiple_tabs_same_user_presence(self):
        async def _run():
            mgr = ChatConnectionManager()
            user_id = 7
            group_ids = [101, 102]

            ws1 = AsyncMock()
            ws2 = AsyncMock()

            with patch("app.services.redis_service.start_group_subscriber", new_callable=AsyncMock) as mock_sub, \
                 patch("app.services.redis_service.set_user_offline", new_callable=AsyncMock) as mock_offline:

                # Tab 1 connects
                conn1 = await mgr.connect(ws1, user_id, group_ids)
                assert conn1 is not None
                assert mgr.get_user_connection_count(user_id) == 1
                assert mgr.is_user_connected(user_id) is True

                # Tab 2 connects for same user
                conn2 = await mgr.connect(ws2, user_id, group_ids)
                assert conn2 != conn1
                assert mgr.get_user_connection_count(user_id) == 2

                # Deliver group event — both tabs must receive it
                test_event = {"type": "message.new", "text": "hello"}
                await mgr._deliver_group_event(101, test_event)
                ws1.send_json.assert_awaited_with(test_event)
                ws2.send_json.assert_awaited_with(test_event)

                # Tab 1 disconnects
                await mgr.disconnect(conn1)
                assert mgr.get_user_connection_count(user_id) == 1
                assert mgr.is_user_connected(user_id) is True
                # Offline must NOT be called yet!
                mock_offline.assert_not_called()

                # Direct send to user should still reach Tab 2
                direct_event = {"type": "pong"}
                await mgr.send_to_user(user_id, direct_event)
                ws2.send_json.assert_awaited_with(direct_event)

                # Tab 2 disconnects — now user connection count is 0
                await mgr.disconnect(conn2)
                assert mgr.get_user_connection_count(user_id) == 0
                assert mgr.is_user_connected(user_id) is False
                # Now offline MUST be called
                mock_offline.assert_awaited_once_with(user_id)

        asyncio.run(_run())

    def test_remove_user_from_group_evicts_all_user_connections(self):
        async def _run():
            mgr = ChatConnectionManager()
            user_id = 15
            group_id = 205
            ws1 = AsyncMock()
            ws2 = AsyncMock()

            with patch("app.services.redis_service.start_group_subscriber", new_callable=AsyncMock):
                conn1 = await mgr.connect(ws1, user_id, [group_id])
                conn2 = await mgr.connect(ws2, user_id, [group_id])

                assert group_id in mgr._connection_groups[conn1]
                assert group_id in mgr._connection_groups[conn2]

                # Remove user from group mid-session
                await mgr.remove_user_from_group(user_id, group_id)
                assert group_id not in mgr._connection_groups[conn1]
                assert group_id not in mgr._connection_groups[conn2]
                assert group_id not in mgr._user_groups.get(user_id, set())

                # Broadcast to group — neither socket should receive it
                ws1.reset_mock()
                ws2.reset_mock()
                await mgr._deliver_group_event(group_id, {"type": "secret"})
                ws1.send_json.assert_not_called()
                ws2.send_json.assert_not_called()

        asyncio.run(_run())


# ── 3. Typing Event Authorization Tests ─────────────────────────────────

class TestTypingEventAuthorization:
    def test_authorized_member_typing_allowed(self):
        async def _run():
            ws = AsyncMock()
            user_id = 20
            group_id = 300
            event = {"group_id": group_id}

            with patch("app.services.chat_websocket.manager") as mock_mgr, \
                 patch("app.services.redis_service.set_typing", new_callable=AsyncMock) as mock_set_typing:
                
                # User is in group
                mock_mgr._user_groups = {user_id: {group_id}}
                mock_mgr.broadcast_to_group = AsyncMock()

                await _handle_typing(ws, user_id, event, is_typing=True)

                mock_set_typing.assert_awaited_once_with(group_id, user_id, True)
                mock_mgr.broadcast_to_group.assert_awaited_once()
                ws.send_json.assert_not_called()

        asyncio.run(_run())

    def test_unauthorized_non_member_typing_rejected(self):
        async def _run():
            ws = AsyncMock()
            user_id = 20
            group_id = 300
            event = {"group_id": group_id}

            with patch("app.services.chat_websocket.manager") as mock_mgr, \
                 patch("app.services.chat_websocket.SessionLocal") as mock_db_cls, \
                 patch("app.services.redis_service.set_typing", new_callable=AsyncMock) as mock_set_typing:
                
                # User not in in-memory cache
                mock_mgr._user_groups = {user_id: set()}
                mock_mgr.broadcast_to_group = AsyncMock()

                # DB returns no active membership
                mock_db = MagicMock()
                mock_db_cls.return_value = mock_db
                with patch("app.services.chat_websocket.ws_get_membership", return_value=None):
                    await _handle_typing(ws, user_id, event, is_typing=True)

                # Must NOT set Redis typing indicator
                mock_set_typing.assert_not_called()
                # Must NOT broadcast
                mock_mgr.broadcast_to_group.assert_not_called()
                # Must send NOT_MEMBER error
                ws.send_json.assert_awaited_once()
                sent_payload = ws.send_json.call_args[0][0]
                assert sent_payload["type"] == WSEventType.ERROR
                assert sent_payload["code"] == WSErrorCode.NOT_MEMBER

        asyncio.run(_run())

    def test_invalid_typing_payload_rejected(self):
        async def _run():
            ws = AsyncMock()
            user_id = 20
            # Missing group_id
            await _handle_typing(ws, user_id, {}, is_typing=True)
            ws.send_json.assert_awaited_once()
            sent_payload = ws.send_json.call_args[0][0]
            assert sent_payload["code"] == WSErrorCode.INVALID_PAYLOAD

        asyncio.run(_run())


# ── 4. Attempt Linking Authorization Tests ──────────────────────────────

class TestAttemptLinkAuthorization:
    def test_linking_own_attempt_succeeds(self):
        db = MagicMock()
        attempt = MagicMock(spec=GroupInterviewAttempt)
        attempt.id = 1
        attempt.user_id = 10
        attempt.share_id = 5
        attempt.share = MagicMock()
        attempt.share.group_id = 2

        session = MagicMock(spec=InterviewSession)
        session.id = 50
        session.user_id = 10

        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.side_effect = [attempt, session]
        db.query.return_value = query_mock

        with patch("app.services.chat_service.require_group_exists"), \
             patch("app.services.chat_service.require_membership"):
            res = link_attempt_to_session(
                db=db,
                attempt_id=1,
                interview_session_id=50,
                user_id=10,
                group_id=2,
                share_id=5,
            )
            assert res.interview_session_id == 50
            assert res.status == AttemptStatus.IN_PROGRESS
            db.commit.assert_called_once()

    def test_user_cannot_link_another_users_attempt(self):
        db = MagicMock()
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.return_value = None
        db.query.return_value = query_mock

        with pytest.raises(HTTPException) as exc_info:
            link_attempt_to_session(
                db=db,
                attempt_id=1,
                interview_session_id=50,
                user_id=99,  # Attacker
                group_id=2,
                share_id=5,
            )
        assert exc_info.value.status_code == 404

    def test_user_cannot_link_session_belonging_to_another_candidate(self):
        db = MagicMock()
        attempt = MagicMock(spec=GroupInterviewAttempt)
        attempt.id = 1
        attempt.user_id = 10
        attempt.share_id = 5
        attempt.share = MagicMock()
        attempt.share.group_id = 2

        # When querying for session with user_id == 10, None is returned because session belongs to 99
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.first.side_effect = [attempt, None]
        db.query.return_value = query_mock

        with patch("app.services.chat_service.require_group_exists"), \
             patch("app.services.chat_service.require_membership"):
            with pytest.raises(HTTPException) as exc_info:
                link_attempt_to_session(
                    db=db,
                    attempt_id=1,
                    interview_session_id=50,
                    user_id=10,
                    group_id=2,
                    share_id=5,
                )
            assert exc_info.value.status_code == 404


