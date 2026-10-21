/**
 * SmartInterview — Chat Context
 *
 * Provides:
 *   - WebSocket connection management with exponential backoff reconnect
 *   - Group list and message state
 *   - Optimistic message sending
 *   - Typing indicators and presence
 *   - Unread counts
 *
 * WebSocket event protocol mirrors backend WSEventType constants.
 */

import {
  createContext, useContext, useState, useEffect, useRef,
  useCallback, useMemo,
} from 'react';
import { useAuth } from './AuthContext';
import chatApi from '../services/chatApi';

const ChatContext = createContext(null);

// ── WebSocket Event Types (must match backend WSEventType) ──────────────────
export const WS_EVENTS = {
  MESSAGE_SEND: 'message.send',
  TYPING_START: 'typing.start',
  TYPING_STOP: 'typing.stop',
  PING: 'ping',
  HEARTBEAT: 'presence.heartbeat',

  MESSAGE_ACK: 'message.ack',
  MESSAGE_NEW: 'message.new',
  TYPING: 'typing',
  PRESENCE: 'presence',
  PONG: 'pong',
  ERROR: 'error',
  INTERVIEW_SHARED: 'interview.shared',
  RESULT_PUBLISHED: 'interview.result_published',
  MEMBER_JOINED: 'member.joined',
  MEMBER_LEFT: 'member.left',
};

// ── Backoff config ────────────────────────────────────────────────────────
const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 30000;

function computeBackoff(attempt) {
  return Math.min(BACKOFF_BASE_MS * Math.pow(2, attempt), BACKOFF_MAX_MS);
}

function getWsUrl({ token, ticket }) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  if (ticket) {
    return `${protocol}//${host}/ws/chat?ticket=${encodeURIComponent(ticket)}`;
  }
  return `${protocol}//${host}/ws/chat?token=${encodeURIComponent(token)}`;
}

export function ChatProvider({ children }) {
  const { user, isAuthenticated } = useAuth();

  // ── State ────────────────────────────────────────────────────────────────
  const [groups, setGroups] = useState([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  // messages: { [groupId]: MessageObject[] }
  const [messages, setMessages] = useState({});
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [hasMore, setHasMore] = useState({});        // { [groupId]: bool }
  const [nextCursor, setNextCursor] = useState({});  // { [groupId]: int | null }
  // typingUsers: { [groupId]: { [userId]: userName } }
  const [typingUsers, setTypingUsers] = useState({});
  const [wsStatus, setWsStatus] = useState('disconnected'); // connected | connecting | disconnected

  // ── Refs ─────────────────────────────────────────────────────────────────
  const wsRef = useRef(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef(null);
  const heartbeatTimer = useRef(null);
  const isConnecting = useRef(false);
  const pendingMessages = useRef({}); // { [clientMessageId]: optimisticMsg }
  const typingTimers = useRef({});    // debounce typing stop
  const isTyping = useRef({});        // { [groupId]: bool }

  // ── Load groups ───────────────────────────────────────────────────────────
  const loadGroups = useCallback(async () => {
    if (!isAuthenticated) return;
    setGroupsLoading(true);
    try {
      const res = await chatApi.listGroups();
      setGroups(res.data.groups || []);
    } catch (e) {
      console.error('Failed to load groups', e);
    } finally {
      setGroupsLoading(false);
    }
  }, [isAuthenticated]);

  // ── Load messages for a group (initial or pagination) ────────────────────
  const loadMessages = useCallback(async (groupId, before = null) => {
    if (!groupId) return;
    setMessagesLoading(true);
    try {
      const params = { limit: 50 };
      if (before) params.before = before;
      const res = await chatApi.getMessages(groupId, params);
      const { messages: msgs, has_more, next_cursor } = res.data;

      setMessages(prev => {
        const existing = prev[groupId] || [];
        if (before) {
          // Prepend older messages (scroll up)
          return { ...prev, [groupId]: [...msgs, ...existing] };
        }
        return { ...prev, [groupId]: msgs };
      });
      setHasMore(prev => ({ ...prev, [groupId]: has_more }));
      setNextCursor(prev => ({ ...prev, [groupId]: next_cursor }));
    } catch (e) {
      console.error('Failed to load messages', e);
    } finally {
      setMessagesLoading(false);
    }
  }, []);

  // ── Mark group as read ────────────────────────────────────────────────────
  const markGroupRead = useCallback(async (groupId) => {
    const msgs = messages[groupId];
    if (!msgs || msgs.length === 0) return;
    const lastId = msgs[msgs.length - 1].id;
    try {
      await chatApi.markRead(groupId, lastId);
      setGroups(prev => prev.map(g =>
        g.id === groupId ? { ...g, unread_count: 0 } : g
      ));
    } catch (e) { /* silent */ }
  }, [messages]);

  // ── Select group ──────────────────────────────────────────────────────────
  const selectGroup = useCallback((groupId) => {
    setSelectedGroupId(groupId);
    if (groupId && !messages[groupId]) {
      loadMessages(groupId);
    }
  }, [messages, loadMessages]);

  // ── WebSocket ─────────────────────────────────────────────────────────────

  const sendWs = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const handleWsMessage = useCallback((event) => {
    let data;
    try { data = JSON.parse(event.data); }
    catch { return; }

    switch (data.type) {
      case WS_EVENTS.MESSAGE_ACK: {
        // Replace optimistic message with confirmed one
        const { client_message_id, message_id, timestamp } = data;
        setMessages(prev => {
          const updated = {};
          for (const [gid, msgs] of Object.entries(prev)) {
            updated[gid] = msgs.map(m =>
              m.client_message_id === client_message_id
                ? { ...m, id: message_id, status: 'sent', created_at: timestamp }
                : m
            );
          }
          return updated;
        });
        delete pendingMessages.current[client_message_id];
        break;
      }

      case WS_EVENTS.MESSAGE_NEW: {
        const msg = data.message;
        if (!msg) break;
        setMessages(prev => {
          const existing = prev[msg.group_id] || [];
          // Don't add duplicates
          if (existing.some(m => m.id === msg.id)) return prev;
          return { ...prev, [msg.group_id]: [...existing, msg] };
        });
        // Update group preview and unread
        setGroups(prev => prev.map(g =>
          g.id === msg.group_id
            ? {
                ...g,
                last_message: msg,
                unread_count: selectedGroupId === msg.group_id
                  ? 0
                  : (g.unread_count || 0) + 1,
              }
            : g
        ).sort((a, b) => {
          const ta = a.last_message?.created_at || a.created_at;
          const tb = b.last_message?.created_at || b.created_at;
          return new Date(tb) - new Date(ta);
        }));
        break;
      }

      case WS_EVENTS.INTERVIEW_SHARED:
      case WS_EVENTS.RESULT_PUBLISHED: {
        const msg = data.message;
        if (!msg) break;
        setMessages(prev => {
          const existing = prev[msg.group_id] || [];
          if (existing.some(m => m.id === msg.id)) return prev;
          return { ...prev, [msg.group_id]: [...existing, msg] };
        });
        setGroups(prev => prev.map(g =>
          g.id === msg.group_id ? { ...g, last_message: msg } : g
        ));
        break;
      }

      case WS_EVENTS.TYPING: {
        const { group_id, user_id, is_typing } = data;
        if (user_id === user?.id) break; // ignore own typing
        setTypingUsers(prev => {
          const group = { ...(prev[group_id] || {}) };
          if (is_typing) {
            group[user_id] = data.user_name || `User ${user_id}`;
          } else {
            delete group[user_id];
          }
          return { ...prev, [group_id]: group };
        });
        break;
      }

      case WS_EVENTS.MEMBER_JOINED:
      case WS_EVENTS.MEMBER_LEFT:
        // Refresh group detail
        loadGroups();
        break;

      case WS_EVENTS.ERROR:
        console.warn('Chat WS error:', data.code, data.message);
        break;

      case WS_EVENTS.PONG:
        break;

      default:
        break;
    }
  }, [user?.id, selectedGroupId, loadGroups]);

  const connectWs = useCallback(async () => {
    if (!isAuthenticated || isConnecting.current) return;
    const token = localStorage.getItem('token');
    if (!token) return;

    isConnecting.current = true;
    setWsStatus('connecting');

    let ticket = null;
    try {
      const ticketRes = await chatApi.getWsTicket();
      ticket = ticketRes.data?.ticket;
    } catch {
      // Fallback to legacy token param
    }

    const ws = new WebSocket(getWsUrl({ token, ticket }));
    wsRef.current = ws;

    ws.onopen = () => {
      isConnecting.current = false;
      reconnectAttempt.current = 0;
      setWsStatus('connected');

      // Heartbeat every 30s
      heartbeatTimer.current = setInterval(() => {
        sendWs({ type: WS_EVENTS.HEARTBEAT });
      }, HEARTBEAT_INTERVAL_MS);
    };

    ws.onmessage = handleWsMessage;

    ws.onclose = (e) => {
      isConnecting.current = false;
      setWsStatus('disconnected');
      clearInterval(heartbeatTimer.current);

      // Don't reconnect if intentionally closed
      if (e.code === 4001) return; // auth failure

      const delay = computeBackoff(reconnectAttempt.current);
      reconnectAttempt.current += 1;
      reconnectTimer.current = setTimeout(connectWs, delay);
    };

    ws.onerror = () => {
      isConnecting.current = false;
    };
  }, [isAuthenticated, handleWsMessage, sendWs]);

  const disconnectWs = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    clearInterval(heartbeatTimer.current);
    if (wsRef.current) {
      wsRef.current.onclose = null; // prevent auto-reconnect
      wsRef.current.close();
      wsRef.current = null;
    }
    setWsStatus('disconnected');
    isConnecting.current = false;
    reconnectAttempt.current = 0;
  }, []);

  // ── Connect / disconnect on auth change ───────────────────────────────────
  useEffect(() => {
    if (isAuthenticated) {
      loadGroups();
      connectWs();
    } else {
      disconnectWs();
      setGroups([]);
      setMessages({});
    }
    return () => disconnectWs();
  }, [isAuthenticated]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Mark read when opening a group ───────────────────────────────────────
  useEffect(() => {
    if (selectedGroupId && messages[selectedGroupId]?.length > 0) {
      markGroupRead(selectedGroupId);
    }
  }, [selectedGroupId, messages]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Send message (optimistic) ─────────────────────────────────────────────
  const sendMessage = useCallback((groupId, text) => {
    if (!text.trim() || !groupId) return;
    const clientMessageId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    // Optimistic message
    const optimistic = {
      id: `opt-${clientMessageId}`,
      group_id: groupId,
      sender_id: user?.id,
      sender_name: user?.name,
      message_type: 'TEXT',
      content: { text: text.trim() },
      client_message_id: clientMessageId,
      created_at: new Date().toISOString(),
      status: 'sending',
    };
    pendingMessages.current[clientMessageId] = optimistic;
    setMessages(prev => ({
      ...prev,
      [groupId]: [...(prev[groupId] || []), optimistic],
    }));

    sendWs({
      type: WS_EVENTS.MESSAGE_SEND,
      group_id: groupId,
      content: text.trim(),
      client_message_id: clientMessageId,
    });
  }, [user, sendWs]);

  // ── Typing indicators (debounced) ─────────────────────────────────────────
  const sendTypingStart = useCallback((groupId) => {
    if (isTyping.current[groupId]) return;
    isTyping.current[groupId] = true;
    sendWs({ type: WS_EVENTS.TYPING_START, group_id: groupId });
  }, [sendWs]);

  const sendTypingStop = useCallback((groupId) => {
    if (!isTyping.current[groupId]) return;
    isTyping.current[groupId] = false;
    sendWs({ type: WS_EVENTS.TYPING_STOP, group_id: groupId });
  }, [sendWs]);

  const handleTyping = useCallback((groupId) => {
    sendTypingStart(groupId);
    clearTimeout(typingTimers.current[groupId]);
    typingTimers.current[groupId] = setTimeout(() => {
      sendTypingStop(groupId);
    }, 2000);
  }, [sendTypingStart, sendTypingStop]);

  // ── Group management helpers ──────────────────────────────────────────────
  const createGroup = useCallback(async (data) => {
    const res = await chatApi.createGroup(data);
    await loadGroups();
    return res.data;
  }, [loadGroups]);

  const addMembers = useCallback(async (groupId, userIds) => {
    await chatApi.addMembers(groupId, userIds);
    await loadGroups();
  }, [loadGroups]);

  const removeMember = useCallback(async (groupId, userId) => {
    await chatApi.removeMember(groupId, userId);
    await loadGroups();
  }, [loadGroups]);

  const promoteAdmin = useCallback(async (groupId, userId) => {
    await chatApi.promoteAdmin(groupId, userId);
    await loadGroups();
  }, [loadGroups]);

  const demoteAdmin = useCallback(async (groupId, userId) => {
    await chatApi.demoteAdmin(groupId, userId);
    await loadGroups();
  }, [loadGroups]);

  // ── Total unread count for badge ──────────────────────────────────────────
  const totalUnread = useMemo(
    () => groups.reduce((sum, g) => sum + (g.unread_count || 0), 0),
    [groups]
  );

  const value = {
    groups, groupsLoading, loadGroups,
    selectedGroupId, selectGroup,
    messages, messagesLoading, loadMessages, hasMore, nextCursor,
    typingUsers,
    wsStatus,
    totalUnread,
    sendMessage,
    handleTyping,
    createGroup, addMembers, removeMember,
    promoteAdmin, demoteAdmin,
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChat must be used within ChatProvider');
  return ctx;
}
