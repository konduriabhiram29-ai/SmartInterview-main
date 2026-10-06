/**
 * GroupDetailsModal — Group information, member management,
 * multi-admin controls, and Admin Interview Results Dashboard.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  X, Users, Shield, ShieldAlert, UserMinus, UserPlus,
  Trophy, Share2, LogOut, Trash2, Search, Check, AlertCircle,
  CheckCircle2, Clock
} from 'lucide-react';
import chatApi from '../../services/chatApi';
import { useAuth } from '../../context/AuthContext';
import { useChat } from '../../context/ChatContext';

export default function GroupDetailsModal({ groupId, isOpen, onClose, onGroupUpdated }) {
  const { user } = useAuth();
  const { loadGroups, selectGroup } = useChat();

  const [activeTab, setActiveTab] = useState('members'); // 'members' | 'results' | 'settings'
  const [group, setGroup] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // User search for adding members
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState([]);
  const [addingMembers, setAddingMembers] = useState(false);

  // Results Dashboard state
  const [resultsData, setResultsData] = useState([]);
  const [loadingResults, setLoadingResults] = useState(false);
  const [publishingUser, setPublishingUser] = useState(null);

  // Fetch full group details
  const fetchGroup = useCallback(async () => {
    if (!groupId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await chatApi.getGroup(groupId);
      setGroup(res.data);
    } catch (err) {
      setError('Failed to load group details.');
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useEffect(() => {
    if (isOpen && groupId) {
      fetchGroup();
      setActiveTab('members');
      setActionSuccess(null);
      setError(null);
      setSearchQuery('');
      setSearchResults([]);
      setSelectedUserIds([]);
    }
  }, [isOpen, groupId, fetchGroup]);

  // Determine current user's role
  const myMembership = group?.members?.find((m) => m.user_id === user?.id);
  const isAdmin = myMembership?.role === 'ADMIN';
  const isCreator = group?.created_by === user?.id;

  // Search users to add
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await chatApi.searchUsers(searchQuery.trim());
        // Filter out already active members
        const currentMemberIds = new Set((group?.members || []).map((m) => m.user_id));
        setSearchResults((res.data || []).filter((u) => !currentMemberIds.has(u.id)));
      } catch (e) {
        console.error('Failed to search users', e);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, group]);

  // Add members
  const handleAddMembers = async () => {
    if (selectedUserIds.length === 0) return;
    setAddingMembers(true);
    setError(null);
    try {
      await chatApi.addMembers(groupId, selectedUserIds);
      setActionSuccess('Members added successfully!');
      setSelectedUserIds([]);
      setSearchQuery('');
      await fetchGroup();
      await loadGroups();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add members.');
    } finally {
      setAddingMembers(false);
    }
  };

  // Remove member
  const handleRemoveMember = async (targetUserId) => {
    if (!window.confirm('Are you sure you want to remove this member?')) return;
    try {
      await chatApi.removeMember(groupId, targetUserId);
      setActionSuccess('Member removed.');
      await fetchGroup();
      await loadGroups();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove member.');
    }
  };

  // Promote to admin
  const handlePromote = async (targetUserId) => {
    try {
      await chatApi.promoteAdmin(groupId, targetUserId);
      setActionSuccess('Member promoted to Admin.');
      await fetchGroup();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to promote member.');
    }
  };

  // Demote admin
  const handleDemote = async (targetUserId) => {
    try {
      await chatApi.demoteAdmin(groupId, targetUserId);
      setActionSuccess('Admin privileges revoked.');
      await fetchGroup();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to demote admin.');
    }
  };

  // Leave group
  const handleLeaveGroup = async () => {
    if (!window.confirm('Are you sure you want to leave this group?')) return;
    try {
      await chatApi.leaveGroup(groupId);
      await loadGroups();
      selectGroup(null);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to leave group.');
    }
  };

  // Delete group
  const handleDeleteGroup = async () => {
    if (!window.confirm('Are you sure you want to permanently delete this group?')) return;
    try {
      await chatApi.deleteGroup(groupId);
      await loadGroups();
      selectGroup(null);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete group.');
    }
  };

  // Load Interview Shares & Results
  const loadInterviewResults = useCallback(async () => {
    if (!groupId) return;
    setLoadingResults(true);
    try {
      // Find interview shares by checking group shares or fetching via chatApi
      // If group has shares list or message list, or load share result
      if (group?.shares && group.shares.length > 0) {
        const allResults = [];
        for (const s of group.shares) {
          try {
            const res = await chatApi.getShareResults(groupId, s.id);
            allResults.push({ share: s, attempts: res.data.attempts || [] });
          } catch (e) {
            console.error('Failed to get share results', e);
          }
        }
        setResultsData(allResults);
      } else {
        // Fallback: fetch group detail with shares
        const gRes = await chatApi.getGroup(groupId);
        if (gRes.data.shares) {
          const allResults = [];
          for (const s of gRes.data.shares) {
            const res = await chatApi.getShareResults(groupId, s.id);
            allResults.push({ share: s, attempts: res.data.attempts || [] });
          }
          setResultsData(allResults);
        }
      }
    } catch (err) {
      console.error('Error fetching interview results:', err);
    } finally {
      setLoadingResults(false);
    }
  }, [groupId, group]);

  useEffect(() => {
    if (activeTab === 'results') {
      loadInterviewResults();
    }
  }, [activeTab, loadInterviewResults]);

  // Publish candidate result to chat
  const handlePublishResult = async (shareId, candidateUserId) => {
    setPublishingUser(candidateUserId);
    setError(null);
    try {
      await chatApi.publishResult(groupId, shareId, candidateUserId);
      setActionSuccess('Result successfully published to group chat!');
      await loadInterviewResults();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to publish result.');
    } finally {
      setPublishingUser(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden flex flex-col max-h-[88vh] border border-slate-100">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-base shadow-xs">
              {group?.name?.charAt(0).toUpperCase() || 'G'}
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800 leading-tight">
                {group?.name || 'Group Details'}
              </h2>
              <p className="text-xs text-slate-500">
                {group?.members?.length || 0} members · {group?.description || 'No description'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer border-none bg-transparent"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-100 px-6 gap-6 bg-slate-50/50 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('members')}
            className={`py-3 border-b-2 flex items-center gap-1.5 cursor-pointer bg-transparent border-t-0 border-x-0 ${
              activeTab === 'members'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Users size={14} />
            Members ({group?.members?.length || 0})
          </button>

          {isAdmin && (
            <button
              onClick={() => setActiveTab('results')}
              className={`py-3 border-b-2 flex items-center gap-1.5 cursor-pointer bg-transparent border-t-0 border-x-0 ${
                activeTab === 'results'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Trophy size={14} />
              Interview Results & Publishing
            </button>
          )}

          <button
            onClick={() => setActiveTab('settings')}
            className={`py-3 border-b-2 flex items-center gap-1.5 cursor-pointer bg-transparent border-t-0 border-x-0 ${
              activeTab === 'settings'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Shield size={14} />
            Group Settings
          </button>
        </div>

        {/* Alerts */}
        <div className="px-6 pt-3 space-y-2">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">
              <AlertCircle size={15} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {actionSuccess && (
            <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl">
              <CheckCircle2 size={15} className="flex-shrink-0" />
              <span>{actionSuccess}</span>
            </div>
          )}
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {/* TAB 1: MEMBERS */}
          {activeTab === 'members' && (
            <div className="space-y-5">
              {/* Add Member section (Admin only) */}
              {isAdmin && (
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/70 space-y-3">
                  <p className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                    <UserPlus size={14} className="text-indigo-600" />
                    Add New Members
                  </p>
                  <div className="relative">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search users by name or email..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  {searching && (
                    <p className="text-xs text-slate-400 py-1">Searching candidates...</p>
                  )}

                  {searchResults.length > 0 && (
                    <div className="max-h-36 overflow-y-auto divide-y divide-slate-100 bg-white border border-slate-200 rounded-lg">
                      {searchResults.map((u) => {
                        const isSelected = selectedUserIds.includes(u.id);
                        return (
                          <div
                            key={u.id}
                            onClick={() => {
                              setSelectedUserIds((prev) =>
                                isSelected ? prev.filter((id) => id !== u.id) : [...prev, u.id]
                              );
                            }}
                            className={`p-2.5 flex items-center justify-between text-xs cursor-pointer hover:bg-slate-50 ${
                              isSelected ? 'bg-indigo-50/60' : ''
                            }`}
                          >
                            <div>
                              <p className="font-semibold text-slate-800">{u.name}</p>
                              <p className="text-[11px] text-slate-400">{u.email}</p>
                            </div>
                            <div className={`w-4 h-4 rounded-md border flex items-center justify-center ${
                              isSelected ? 'bg-indigo-600 border-indigo-600 text-white' : 'border-slate-300'
                            }`}>
                              {isSelected && <Check size={11} strokeWidth={3} />}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {selectedUserIds.length > 0 && (
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-xs text-slate-600">
                        {selectedUserIds.length} user(s) selected
                      </span>
                      <button
                        onClick={handleAddMembers}
                        disabled={addingMembers}
                        className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer border-none transition-colors"
                      >
                        {addingMembers ? 'Adding...' : 'Add Selected'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Members List */}
              <div className="space-y-2">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Current Members ({group?.members?.length || 0})
                </p>

                <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-xl overflow-hidden">
                  {group?.members?.map((m) => {
                    const isTargetAdmin = m.role === 'ADMIN';
                    const isSelf = m.user_id === user?.id;

                    return (
                      <div
                        key={m.id || m.user_id}
                        className="p-3.5 flex items-center justify-between gap-3 hover:bg-slate-50 transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center font-bold text-xs flex-shrink-0">
                            {m.user_name?.charAt(0).toUpperCase() || 'U'}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="text-xs font-bold text-slate-800 truncate">
                                {m.user_name}
                              </p>
                              {isSelf && (
                                <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-medium">
                                  You
                                </span>
                              )}
                              {isTargetAdmin && (
                                <span className="inline-flex items-center gap-1 text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200/60 px-1.5 py-0.2 rounded-md font-semibold">
                                  <Shield size={10} />
                                  Admin
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-400 truncate">{m.user_email}</p>
                          </div>
                        </div>

                        {/* Admin controls for other users */}
                        {isAdmin && !isSelf && (
                          <div className="flex items-center gap-1 flex-shrink-0">
                            {isTargetAdmin ? (
                              <button
                                onClick={() => handleDemote(m.user_id)}
                                title="Demote from Admin"
                                className="px-2 py-1 text-[11px] font-medium text-amber-700 hover:bg-amber-50 rounded-md border border-amber-200 transition-colors cursor-pointer bg-transparent"
                              >
                                Demote
                              </button>
                            ) : (
                              <button
                                onClick={() => handlePromote(m.user_id)}
                                title="Promote to Admin"
                                className="px-2 py-1 text-[11px] font-medium text-indigo-700 hover:bg-indigo-50 rounded-md border border-indigo-200 transition-colors cursor-pointer bg-transparent"
                              >
                                Make Admin
                              </button>
                            )}

                            <button
                              onClick={() => handleRemoveMember(m.user_id)}
                              title="Remove from Group"
                              className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors cursor-pointer border-none bg-transparent"
                            >
                              <UserMinus size={15} />
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: INTERVIEW RESULTS & PUBLISHING (Admin Dashboard) */}
          {activeTab === 'results' && (
            <div className="space-y-5">
              <div className="bg-indigo-50/70 border border-indigo-100 rounded-xl p-3.5">
                <h3 className="text-xs font-bold text-indigo-900 mb-1 flex items-center gap-1.5">
                  <Trophy size={14} className="text-indigo-600" />
                  Candidate Results Dashboard
                </h3>
                <p className="text-[11px] text-indigo-700 leading-relaxed">
                  Candidate scores remain private by default. As an Admin, you can review member submissions
                  and selectively publish standout performances to the group chat.
                </p>
              </div>

              {loadingResults ? (
                <div className="space-y-3 py-4">
                  {[1, 2].map((i) => (
                    <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : resultsData.length === 0 ? (
                <div className="text-center py-8">
                  <Share2 size={24} className="mx-auto text-slate-300 mb-2" />
                  <p className="text-xs font-semibold text-slate-600">No interviews shared yet</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Share an interview session from the chat to invite submissions.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {resultsData.map(({ share, attempts }) => (
                    <div
                      key={share.id}
                      className="border border-slate-200 rounded-xl p-4 space-y-3 bg-white shadow-xs"
                    >
                      <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                        <div>
                          <p className="text-xs font-bold text-slate-800">
                            Interview #{share.id} · Session #{share.interview_session_id}
                          </p>
                          <p className="text-[10px] text-slate-400">
                            Shared on {new Date(share.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          {attempts.length} Attempt(s)
                        </span>
                      </div>

                      {attempts.length === 0 ? (
                        <p className="text-xs text-slate-400 italic py-2">
                          No members have attempted this interview yet.
                        </p>
                      ) : (
                        <div className="divide-y divide-slate-100">
                          {attempts.map((att) => (
                            <div
                              key={att.id}
                              className="py-2.5 flex items-center justify-between gap-3 text-xs"
                            >
                              <div>
                                <p className="font-semibold text-slate-800">{att.user_name}</p>
                                <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500">
                                  <span>Status: <strong className="capitalize">{att.status}</strong></span>
                                  {att.overall_score != null && (
                                    <span className="font-bold text-indigo-600">
                                      Score: {att.overall_score}%
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="flex items-center gap-2">
                                {att.is_published ? (
                                  <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-md font-semibold">
                                    <Check size={12} />
                                    Published
                                  </span>
                                ) : att.status === 'completed' ? (
                                  <button
                                    onClick={() => handlePublishResult(share.id, att.user_id)}
                                    disabled={publishingUser === att.user_id}
                                    className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer border-none transition-colors flex items-center gap-1"
                                  >
                                    {publishingUser === att.user_id ? 'Publishing...' : 'Publish to Group'}
                                  </button>
                                ) : (
                                  <span className="text-[11px] text-slate-400 italic flex items-center gap-1">
                                    <Clock size={11} />
                                    In Progress
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: SETTINGS & LEAVE */}
          {activeTab === 'settings' && (
            <div className="space-y-5">
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
                <p className="text-xs font-bold text-slate-700 uppercase tracking-wider">Group Information</p>
                <div>
                  <p className="text-[11px] text-slate-400">Group Name</p>
                  <p className="text-sm font-semibold text-slate-800">{group?.name}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-400">Description</p>
                  <p className="text-xs text-slate-600">{group?.description || 'None'}</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-400">Created At</p>
                  <p className="text-xs text-slate-600">
                    {group?.created_at ? new Date(group.created_at).toLocaleDateString() : 'N/A'}
                  </p>
                </div>
              </div>

              {/* Danger Zone */}
              <div className="border border-red-200 rounded-xl p-4 bg-red-50/40 space-y-3">
                <p className="text-xs font-bold text-red-800 uppercase tracking-wider">Danger Zone</p>
                <div className="flex flex-col gap-2">
                  <button
                    onClick={handleLeaveGroup}
                    className="w-full py-2 px-3 text-xs font-semibold text-red-700 bg-white hover:bg-red-50 border border-red-200 rounded-lg flex items-center justify-center gap-1.5 cursor-pointer transition-colors"
                  >
                    <LogOut size={14} />
                    Leave Group
                  </button>

                  {isCreator && (
                    <button
                      onClick={handleDeleteGroup}
                      className="w-full py-2 px-3 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg flex items-center justify-center gap-1.5 cursor-pointer border-none transition-colors"
                    >
                      <Trash2 size={14} />
                      Delete Group
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
