/**
 * SmartInterview — Chat API Service
 * REST calls for all chat operations.
 * WebSocket is managed separately in ChatContext.
 */

import api from './api';

// ── Groups ──────────────────────────────────────────────────────────────────

export const chatApi = {
  // Groups
  listGroups: () => api.get('/chat/groups'),
  getGroup: (groupId) => api.get(`/chat/groups/${groupId}`),
  createGroup: (data) => api.post('/chat/groups', data),
  updateGroup: (groupId, data) => api.patch(`/chat/groups/${groupId}`, data),
  deleteGroup: (groupId) => api.delete(`/chat/groups/${groupId}`),

  // Members
  addMembers: (groupId, userIds) =>
    api.post(`/chat/groups/${groupId}/members`, { user_ids: userIds }),
  removeMember: (groupId, userId) =>
    api.delete(`/chat/groups/${groupId}/members/${userId}`),
  leaveGroup: (groupId) =>
    api.delete(`/chat/groups/${groupId}/leave`),

  // Admin management
  promoteAdmin: (groupId, userId) =>
    api.post(`/chat/groups/${groupId}/admins/${userId}`),
  demoteAdmin: (groupId, userId) =>
    api.delete(`/chat/groups/${groupId}/admins/${userId}`),

  // Messages
  getMessages: (groupId, params = {}) =>
    api.get(`/chat/groups/${groupId}/messages`, { params }),
  markRead: (groupId, messageId) =>
    api.post(`/chat/groups/${groupId}/read`, { message_id: messageId }),

  // User search
  searchUsers: (q) => api.get('/chat/users/search', { params: { q } }),

  // Interview sharing
  shareInterview: (groupId, sessionId) =>
    api.post(`/chat/groups/${groupId}/interviews`, {
      interview_session_id: sessionId,
    }),
  startAttempt: (groupId, shareId) =>
    api.post(`/chat/groups/${groupId}/interviews/${shareId}/attempt`),
  linkAttempt: (groupId, shareId, attemptId, sessionId) =>
    api.post(
      `/chat/groups/${groupId}/interviews/${shareId}/attempt/${attemptId}/link`,
      null,
      { params: { interview_session_id: sessionId } }
    ),

  // Results
  getShareResults: (groupId, shareId) =>
    api.get(`/chat/groups/${groupId}/interviews/${shareId}/results`),
  publishResult: (groupId, shareId, userId) =>
    api.post(`/chat/groups/${groupId}/interviews/${shareId}/publish/${userId}`),

  // WebSocket Ticket (scoped, short-lived credential)
  getWsTicket: () => api.post('/chat/ws-ticket'),

  // My interviews (for share selector — reuse existing)
  getMyInterviews: () => api.get('/interviews/history'),
};

export default chatApi;
