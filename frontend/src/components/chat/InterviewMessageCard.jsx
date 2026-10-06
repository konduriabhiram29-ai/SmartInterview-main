/**
 * InterviewMessageCard — renders a shared interview in the chat.
 * Shown when message_type === 'INTERVIEW'
 */
import { ClipboardList, ArrowRight, CheckCircle } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import chatApi from '../../services/chatApi';

export default function InterviewMessageCard({ message, groupId }) {
  const { content } = message;
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [attempted, setAttempted] = useState(!!content.attempt_id);

  const handleAttempt = async () => {
    if (loading || attempted) return;
    setLoading(true);
    try {
      // 1. Create/get attempt record
      const res = await chatApi.startAttempt(groupId, content.share_id);
      const { attempt_id, original_session } = res.data;

      // 2. Start a new interview session using the same params as original
      const { default: api } = await import('../../services/api');
      const startRes = await api.post('/interviews/start', {
        difficulty: original_session?.difficulty || 'medium',
        question_type: original_session?.question_type || 'mixed',
        question_count: original_session?.question_count || 5,
        selected_skills: original_session?.selected_skills || [],
      });
      const newSessionId = startRes.data.session_id;

      // 3. Link the attempt to the new session
      await chatApi.linkAttempt(groupId, content.share_id, attempt_id, newSessionId);

      setAttempted(true);
      navigate(`/interview/${newSessionId}`);
    } catch (err) {
      console.error('Failed to start attempt', err);
      alert(err?.response?.data?.detail || 'Failed to start interview.');
    } finally {
      setLoading(false);
    }
  };

  const difficulty = content.difficulty || 'medium';
  const diffColor = {
    easy: 'text-emerald-600 bg-emerald-50',
    medium: 'text-amber-600 bg-amber-50',
    hard: 'text-red-600 bg-red-50',
  }[difficulty] || 'text-slate-600 bg-slate-100';

  return (
    <div className="bg-white border border-indigo-100 rounded-xl overflow-hidden
      shadow-sm w-full max-w-[300px]">
      {/* Card header */}
      <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 flex items-center gap-2">
        <ClipboardList size={16} className="text-white/80" />
        <span className="text-white text-xs font-semibold uppercase tracking-wide">
          Interview Session
        </span>
      </div>

      {/* Card body */}
      <div className="p-4">
        <h4 className="font-bold text-slate-900 text-sm mb-2 leading-tight">
          {content.title || 'Technical Interview'}
        </h4>
        <div className="flex items-center gap-3 mb-3">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${diffColor}`}>
            {difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}
          </span>
          <span className="text-xs text-slate-500">
            {content.question_count || 5} Questions
          </span>
        </div>

        {attempted ? (
          <div className="flex items-center gap-2 text-emerald-600 text-sm font-medium">
            <CheckCircle size={16} />
            Attempted
          </div>
        ) : (
          <button
            onClick={handleAttempt}
            disabled={loading}
            className="w-full btn btn-primary text-xs py-2 mt-1"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                Starting...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Attempt Interview <ArrowRight size={14} />
              </span>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
