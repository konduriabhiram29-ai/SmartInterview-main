import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { Clock, FileText, ChevronRight, CheckCircle2, Play } from 'lucide-react';

export default function History() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/interviews/history')
      .then(res => setSessions(res.data))
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  const getScoreTextColor = (score) => {
    if (score >= 80) return 'text-emerald-600';
    if (score >= 60) return 'text-amber-500';
    if (score >= 40) return 'text-orange-500';
    return 'text-red-500';
  };

  if (loading) {
    return (
      <div className="page-container max-w-4xl fade-up">
        <div className="page-header">
          <div className="h-8 w-64 bg-slate-200 rounded-lg animate-pulse mb-2"></div>
          <div className="h-4 w-96 bg-slate-100 rounded-md animate-pulse"></div>
        </div>
        <div className="card overflow-hidden shadow-sm p-0">
          <div className="divide-y divide-slate-100">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex p-5 gap-4">
                <div className="w-12 h-12 bg-slate-100 rounded-xl animate-pulse flex-shrink-0"></div>
                <div className="flex-1 space-y-3 py-1">
                  <div className="h-4 w-1/3 bg-slate-200 rounded animate-pulse"></div>
                  <div className="h-3 w-1/4 bg-slate-100 rounded animate-pulse"></div>
                  <div className="flex gap-2 pt-1">
                    <div className="h-4 w-16 bg-slate-100 rounded animate-pulse"></div>
                    <div className="h-4 w-20 bg-slate-100 rounded animate-pulse"></div>
                  </div>
                </div>
                <div className="w-16 h-8 bg-slate-100 rounded-lg animate-pulse"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container max-w-4xl fade-up">
      <div className="page-header">
        <h1 className="page-title flex items-center gap-2">
          <Clock size={24} className="text-indigo-600" />
          Interview History
        </h1>
        <p className="page-subtitle ml-8">Review your past interview sessions, analyze detailed feedback, and track your progress over time.</p>
      </div>

      {sessions.length === 0 ? (
        <div className="card text-center p-12 bg-slate-50/50 border-dashed">
          <div className="w-16 h-16 bg-white border border-slate-200 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-sm text-slate-400">
            <Clock size={28} />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">No interviews yet</h3>
          <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto">Your interview history will appear here once you complete your first adaptive practice session.</p>
          <Link to="/setup" className="btn btn-primary shadow-md">
            <Play size={16} className="fill-current" />
            Start First Interview
          </Link>
        </div>
      ) : (
        <div className="card overflow-hidden shadow-sm">
          <div className="divide-y divide-slate-100/80">
            {sessions.map((s, idx) => (
              <Link
                key={s.id}
                to={s.status === 'completed' ? `/results/${s.id}` : `/interview/${s.id}`}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-5 hover:bg-slate-50 transition-colors no-underline group gap-4"
              >
                <div className="flex items-start gap-4 min-w-0">
                  <div className="w-12 h-12 bg-indigo-50/50 rounded-xl flex items-center justify-center flex-shrink-0 border border-indigo-100 text-indigo-500 group-hover:bg-indigo-100 group-hover:text-indigo-600 transition-colors">
                    <FileText size={20} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="font-bold text-slate-900 capitalize text-sm">Session #{sessions.length - idx}</span>
                      <span className="text-slate-300 hidden sm:inline">•</span>
                      <span className="text-xs font-semibold text-slate-500 capitalize px-2 py-0.5 bg-slate-100 rounded-md">{s.difficulty}</span>
                      {s.completion_reason && (
                        <>
                          <span className="text-slate-300 hidden sm:inline">•</span>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide border border-slate-200 px-1.5 py-0.5 rounded">
                            {s.completion_reason.replace(/_/g, ' ')}
                          </span>
                        </>
                      )}
                    </div>
                    <div className="text-xs font-medium text-slate-500 mb-3 flex items-center gap-2">
                      <span>{new Date(s.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                      <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                      <span>{s.questions_answered} {s.question_count > 0 ? `/ ${s.question_count}` : ''} answered</span>
                    </div>
                    {s.selected_skills && (
                      <div className="flex flex-wrap gap-1.5">
                        {s.selected_skills.slice(0, 4).map(sk => (
                          <span key={sk} className="badge badge-slate text-[10px]">{sk}</span>
                        ))}
                        {s.selected_skills.length > 4 && (
                          <span className="badge badge-indigo text-[10px]">+{s.selected_skills.length - 4}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center justify-between sm:justify-end gap-6 sm:pl-6 sm:border-l border-slate-100 pt-2 sm:pt-0 border-t sm:border-t-0 mt-2 sm:mt-0">
                  <div className="text-right flex-shrink-0">
                    {s.average_score != null ? (
                      <>
                        <div className={`text-2xl font-extrabold tracking-tight ${getScoreTextColor(s.average_score)}`}>
                          {Math.round(s.average_score)}<span className="text-sm font-bold opacity-60">%</span>
                        </div>
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">Score</div>
                      </>
                    ) : (
                      <span className={`badge ${s.status === 'completed' ? 'badge-success' : s.status === 'abandoned' ? 'badge-error' : 'badge-amber'}`}>
                        {s.status === 'completed' && <CheckCircle2 size={12} className="mr-1" />}
                        {s.status === 'completed' ? 'Completed' : s.status === 'abandoned' ? 'Abandoned' : 'In Progress'}
                      </span>
                    )}
                  </div>
                  <div className="w-8 h-8 rounded-full bg-slate-50 border border-slate-200 flex items-center justify-center text-slate-400 group-hover:bg-indigo-600 group-hover:border-indigo-600 group-hover:text-white transition-all shadow-sm hidden sm:flex">
                    <ChevronRight size={16} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
