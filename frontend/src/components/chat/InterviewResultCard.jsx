/**
 * InterviewResultCard — renders a published result in the chat.
 * Shown when message_type === 'INTERVIEW_RESULT'
 */
import { Trophy, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

function ScoreBar({ label, value }) {
  const pct = Math.max(0, Math.min(100, value || 0));
  const color = pct >= 80 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-24 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-8 text-right">{Math.round(pct)}</span>
    </div>
  );
}

export default function InterviewResultCard({ message }) {
  const { content } = message;
  const { user } = useAuth();
  const navigate = useNavigate();
  const isOwn = user?.id === content.candidate_user_id;

  const score = content.overall_score ?? 0;
  const scoreColor =
    score >= 80 ? 'text-emerald-600' :
    score >= 60 ? 'text-amber-600' :
    'text-red-600';

  return (
    <div className="bg-white border border-amber-100 rounded-xl overflow-hidden
      shadow-sm w-full max-w-[300px]">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2.5 flex items-center gap-2">
        <Trophy size={16} className="text-white/80" />
        <span className="text-white text-xs font-semibold uppercase tracking-wide">
          Interview Result
        </span>
      </div>

      {/* Body */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="font-bold text-slate-900 text-sm">
              {content.candidate_name}
            </div>
            <div className="text-xs text-slate-500">{content.session_title}</div>
          </div>
          <div className={`text-2xl font-bold ${scoreColor}`}>
            {Math.round(score)}
            <span className="text-sm font-normal text-slate-400">/100</span>
          </div>
        </div>

        <div className="space-y-1.5 mb-3">
          <ScoreBar label="Technical" value={content.technical_score} />
          <ScoreBar label="Completeness" value={content.completeness_score} />
          <ScoreBar label="Relevance" value={content.relevance_score} />
        </div>

        {isOwn && content.interview_session_id_for_candidate && (
          <button
            onClick={() => navigate(`/results/${content.interview_session_id_for_candidate}`)}
            className="w-full btn btn-secondary text-xs py-2 mt-1 flex items-center gap-2
              justify-center"
          >
            View Full Result <ExternalLink size={12} />
          </button>
        )}
      </div>
    </div>
  );
}
