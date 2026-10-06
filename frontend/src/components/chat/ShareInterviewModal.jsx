/**
 * ShareInterviewModal — Allows Group Admins to select an interview
 * from their session history and share it to the group chat.
 */

import { useState, useEffect } from 'react';
import { X, Award, Share2, Check, Clock, AlertCircle } from 'lucide-react';
import api from '../../services/api';
import chatApi from '../../services/chatApi';

export default function ShareInterviewModal({ groupId, isOpen, onClose, onShared }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [sharing, setSharing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      setError(null);
      setSelectedId(null);
      api.get('/interviews/history')
        .then((res) => {
          setSessions(res.data || []);
        })
        .catch((err) => {
          setError('Failed to load past interview sessions.');
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleShare = async () => {
    if (!selectedId || !groupId) return;
    setSharing(true);
    setError(null);
    try {
      await chatApi.shareInterview(groupId, selectedId);
      if (onShared) onShared();
      onClose();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to share interview to group.';
      setError(msg);
    } finally {
      setSharing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden flex flex-col max-h-[85vh] border border-slate-100">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <Share2 size={18} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-800">Share Interview to Group</h2>
              <p className="text-xs text-slate-500">Pick an interview session for group members to attempt</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer border-none bg-transparent"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">
              <AlertCircle size={15} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="space-y-3 py-6">
              {[1, 2, 3].map((n) => (
                <div key={n} className="h-16 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-10 px-4">
              <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto mb-3">
                <Clock size={22} />
              </div>
              <h3 className="text-sm font-semibold text-slate-700">No past interviews found</h3>
              <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
                You need to start or complete an interview first before you can share it with your group.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Select an Interview Session:
              </p>
              {sessions.map((s) => {
                const isSelected = selectedId === s.id;
                const skillsStr = (s.selected_skills && s.selected_skills.length > 0)
                  ? s.selected_skills.join(', ')
                  : 'General Skills';
                const dateStr = s.created_at
                  ? new Date(s.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
                  : '';

                return (
                  <div
                    key={s.id}
                    onClick={() => setSelectedId(s.id)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                      isSelected
                        ? 'border-indigo-600 bg-indigo-50/50 shadow-xs'
                        : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-slate-800 truncate">
                          {skillsStr}
                        </span>
                        <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-slate-100 text-slate-600">
                          {s.difficulty || 'Medium'}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span>{dateStr}</span>
                        {s.overall_score != null && (
                          <span className="flex items-center gap-1 font-medium text-slate-600">
                            <Award size={13} className="text-amber-500" />
                            Score: {s.overall_score}%
                          </span>
                        )}
                        <span className="capitalize">{s.status || 'completed'}</span>
                      </div>
                    </div>

                    <div className={`w-5 h-5 rounded-full flex items-center justify-center border transition-all flex-shrink-0 ${
                      isSelected
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'border-slate-300 bg-white'
                    }`}>
                      {isSelected && <Check size={12} strokeWidth={3} />}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/60 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer border-none bg-transparent"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleShare}
            disabled={!selectedId || sharing}
            className={`px-5 py-2 text-xs font-semibold rounded-xl flex items-center gap-2 transition-all ${
              selectedId && !sharing
                ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs cursor-pointer'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            }`}
          >
            {sharing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                Sharing...
              </>
            ) : (
              <>
                <Share2 size={14} />
                Share with Group
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
