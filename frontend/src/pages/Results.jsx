import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { BarChart3, Brain, Target, CheckCircle, ArrowLeft, Lightbulb, Loader2, AlertCircle, ChevronDown, ChevronUp, Download } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';

export default function Results() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedQ, setExpandedQ] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  useEffect(() => { loadResults(); }, [id]);

  const loadResults = async () => {
    try {
      const res = await api.get(`/interviews/${id}/results`);
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const response = await api.get(`/interviews/${id}/report/pdf`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `SmartInterview_Report_Session_${id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Failed to download PDF report. Please ensure the interview is completed and try again.');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const getScoreColorClass = (score) => {
    if (score >= 80) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    if (score >= 60) return 'text-amber-600 bg-amber-50 border-amber-200';
    if (score >= 40) return 'text-orange-600 bg-orange-50 border-orange-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };
  
  const getScoreTextColor = (score) => {
    if (score >= 80) return 'text-emerald-600';
    if (score >= 60) return 'text-amber-500';
    if (score >= 40) return 'text-orange-500';
    return 'text-red-500';
  };

  const getBloomLabel = (level) => {
    const labels = { remember: 'Remember', understand: 'Understand', apply: 'Apply', analyze: 'Analyze', evaluate: 'Evaluate', create: 'Create' };
    return labels[level] || level || '';
  };

  if (loading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="page-container max-w-lg mt-12 fade-up">
        <div className="card text-center p-10 bg-red-50/50 border-red-100">
          <AlertCircle size={40} className="text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-red-900 mb-2">Error Loading Results</h2>
          <p className="text-red-700 mb-6 text-sm">{error}</p>
          <button className="btn btn-primary bg-red-600 hover:bg-red-700 w-full" onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
        </div>
      </div>
    );
  }

  const { session, overall_average_score, skill_performance, bloom_progression, questions, recommendations } = results;
  const hasEvaluations = questions.some(q => q.evaluation);

  return (
    <div className="page-container max-w-5xl fade-up space-y-6">
      
      {/* Header section with score */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-8">
        <div>
          <button onClick={() => navigate('/history')} className="flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-indigo-600 mb-3 bg-transparent border-none cursor-pointer transition-colors p-0 no-underline uppercase tracking-wider">
            <ArrowLeft size={14} /> Back to History
          </button>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Interview Results</h1>
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <span className="badge badge-slate capitalize shadow-sm px-3 py-1">{session.difficulty}</span>
            <span className="text-slate-300">•</span>
            <span className="text-sm font-semibold text-slate-600">{questions.length} questions answered</span>
            <span className="text-slate-300">•</span>
            <span className="badge badge-indigo capitalize shadow-sm px-3 py-1">
              {session.completion_reason ? session.completion_reason.replace(/_/g, ' ') : 'Manual Completion'}
            </span>
          </div>
        </div>
        
        {hasEvaluations && (
          <div className="flex flex-col items-end gap-3 flex-shrink-0">
            <div className="card p-5 bg-white border-slate-200/60 shadow-sm min-w-[160px] text-center flex flex-col items-center justify-center">
              <div className={`text-5xl font-black tracking-tight leading-none ${getScoreTextColor(overall_average_score)}`}>
                {Math.round(overall_average_score)}<span className="text-2xl font-bold opacity-60 ml-1">%</span>
              </div>
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mt-2">Overall Score</div>
            </div>
            
            <button
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              className="btn btn-primary w-full shadow-md py-2.5 text-sm"
            >
              {downloadingPdf ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
              {downloadingPdf ? 'Generating PDF...' : 'Download Full Report'}
            </button>
          </div>
        )}
      </div>

      {!hasEvaluations && (
        <div className="card p-10 text-center bg-slate-50/50 border-dashed mb-8">
          <div className="w-16 h-16 bg-white border border-slate-200 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-sm text-amber-500">
            <AlertCircle size={28} />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">No Evaluated Questions in Session</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto mb-6 leading-relaxed">
            This interview session does not contain completed question evaluations. Start a new interview to receive full technical analysis.
          </p>
          <Link to="/setup" className="btn btn-primary shadow-sm">
            Start New Interview
          </Link>
        </div>
      )}

      {hasEvaluations && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Skill Performance */}
          {Object.keys(skill_performance).length > 0 && (
            <div className="card p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-6 border-b border-slate-100/60 pb-4">
                <Target size={18} className="text-indigo-600" />
                <h2 className="text-base font-bold text-slate-900">Skill Performance</h2>
              </div>
              <div className="space-y-5">
                {Object.entries(skill_performance).map(([skill, data]) => (
                  <div key={skill}>
                    <div className="flex justify-between items-end mb-2">
                      <span className="text-sm font-bold text-slate-700 truncate mr-2">{skill}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded uppercase">{data.questions}Q</span>
                        <span className={`text-sm font-black ${getScoreTextColor(data.average_score)}`}>
                          {Math.round(data.average_score)}%
                        </span>
                      </div>
                    </div>
                    <div className="progress-track bg-slate-100">
                      <div 
                        className={`progress-fill ${
                          data.average_score >= 80 ? 'bg-gradient-to-r from-emerald-400 to-emerald-500' :
                          data.average_score >= 60 ? 'bg-gradient-to-r from-amber-400 to-amber-500' :
                          data.average_score >= 40 ? 'bg-gradient-to-r from-orange-400 to-orange-500' : 'bg-gradient-to-r from-red-400 to-red-500'
                        }`}
                        style={{ width: `${Math.min(100, data.average_score)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Recommendations */}
          {recommendations.length > 0 && (
            <div className="card p-6 shadow-sm border-t-4 border-t-amber-400 flex flex-col">
              <div className="flex items-center gap-2 mb-5 border-b border-slate-100/60 pb-4">
                <Lightbulb size={18} className="text-amber-500" />
                <h2 className="text-base font-bold text-slate-900">AI Recommendations</h2>
              </div>
              <div className="space-y-3 flex-1 overflow-y-auto pr-2">
                {recommendations.map((rec, i) => (
                  <div key={i} className={`p-4 rounded-xl border ${
                    rec.priority === 'high' ? 'bg-red-50/50 border-red-200' : 
                    rec.priority === 'medium' ? 'bg-amber-50/50 border-amber-200' : 'bg-emerald-50/50 border-emerald-200'
                  }`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-extrabold text-slate-900 uppercase tracking-wider">{rec.skill}</span>
                      <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-sm ${
                        rec.priority === 'high' ? 'bg-red-100 text-red-700' : 
                        rec.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
                      }`}>
                        {rec.priority} Priority
                      </span>
                    </div>
                    <div className="text-sm text-slate-600 leading-relaxed font-medium">
                      {rec.message}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Progression Trackers (Bloom + Difficulty) */}
      {(bloom_progression.length > 0 || questions.some(q => q.difficulty)) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Bloom */}
          {bloom_progression.length > 0 && (
            <div className="card p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <Brain size={16} className="text-purple-600" />
                <h2 className="text-sm font-bold text-slate-900">Bloom's Taxonomy Path</h2>
              </div>
              <div className="flex gap-2.5 overflow-x-auto pb-3 pt-1 scrollbar-hide px-1">
                {bloom_progression.map((bp, i) => (
                  <div key={i} className="flex flex-col items-center p-3 rounded-xl bg-white border border-slate-200 shadow-sm min-w-[75px] flex-shrink-0 relative">
                    {i > 0 && <div className="absolute left-[-10px] top-1/2 w-2 h-[2px] bg-slate-200"></div>}
                    <span className="text-[10px] font-extrabold text-slate-400 mb-1">Q{bp.question_number}</span>
                    <span className="text-xs font-bold text-purple-700 mb-1">
                      {getBloomLabel(bp.bloom_level)}
                    </span>
                    <span className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-[10px] font-black text-slate-500">
                      L{bp.bloom_order}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Difficulty */}
          {questions.some(q => q.difficulty) && (
            <div className="card p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <Target size={16} className="text-emerald-600" />
                <h2 className="text-sm font-bold text-slate-900">Difficulty Adaptation</h2>
              </div>
              <div className="flex gap-2.5 overflow-x-auto pb-3 pt-1 scrollbar-hide px-1">
                {questions.map((q, i) => (
                  <div key={q.id || i} className="flex flex-col items-center p-3 rounded-xl bg-white border border-slate-200 shadow-sm min-w-[85px] flex-shrink-0 relative">
                    {i > 0 && <div className="absolute left-[-10px] top-1/2 w-2 h-[2px] bg-slate-200"></div>}
                    <span className="text-[10px] font-extrabold text-slate-400 mb-1">Q{q.question_number}</span>
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md mb-1.5 ${
                      q.difficulty === 'hard' ? 'bg-red-50 text-red-700' :
                      q.difficulty === 'medium' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'
                    }`}>
                      {q.difficulty}
                    </span>
                    <span className="text-[9px] font-semibold text-slate-400 truncate max-w-[70px] uppercase tracking-wider" title={q.skill}>
                      {q.skill}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Question-by-Question Review */}
      <div className="card shadow-sm overflow-hidden mb-8">
        <div className="p-5 border-b border-slate-100/60 bg-slate-50/50">
          <h2 className="text-base font-bold text-slate-900">
            Question Review ({questions.length})
          </h2>
        </div>
        <div className="divide-y divide-slate-100/80">
          {questions.map((q) => {
            const isExpanded = expandedQ === q.id;
            const ev = q.evaluation;
            return (
              <div key={q.id} className="bg-white">
                {/* Summary row */}
                <div 
                  className={`p-4 sm:p-5 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors ${isExpanded ? 'bg-indigo-50/30' : ''}`}
                  onClick={() => setExpandedQ(isExpanded ? null : q.id)}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0 pr-4">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500 flex-shrink-0">
                      Q{q.question_number}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-slate-900 truncate max-w-[150px] sm:max-w-xs">{q.skill}</span>
                        {q.bloom_level && (
                          <span className="badge badge-purple text-[10px] hidden sm:inline-flex">
                            <Brain size={10} className="mr-1" /> {getBloomLabel(q.bloom_level)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-4 flex-shrink-0">
                    {ev ? (
                      <div className="text-right">
                        <span className={`text-lg font-black tracking-tight ${getScoreTextColor(ev.overall_score)}`}>
                          {ev.overall_score}%
                        </span>
                      </div>
                    ) : (
                      <span className="badge badge-slate text-[10px]">No eval</span>
                    )}
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center transition-colors ${isExpanded ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-400'}`}>
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </div>
                  </div>
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="p-5 sm:p-6 border-t border-slate-100 bg-white shadow-inner">
                    <div className="mb-6">
                      <div className="eyebrow mb-2 text-indigo-500">Question</div>
                      <div className="text-base text-slate-900 leading-relaxed font-semibold prose prose-slate max-w-none prose-p:my-1 prose-pre:bg-slate-800 prose-pre:text-slate-100">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.question_text}</ReactMarkdown>
                      </div>
                    </div>
                    
                    {q.answer_text && (
                      <div className="mb-6">
                        <div className="eyebrow mb-2 text-slate-500">Your Answer</div>
                        <div className="text-sm leading-relaxed text-slate-700 bg-slate-50 border border-slate-200 p-4 rounded-xl whitespace-pre-wrap font-medium">
                          {q.answer_text}
                        </div>
                      </div>
                    )}
                    
                    {ev && (
                      <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-5 sm:p-6">
                        <div className="eyebrow text-indigo-600 mb-4 flex items-center gap-2">
                          <BarChart3 size={14} /> Evaluation Breakdown
                        </div>
                        
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
                          {[
                            { l: 'Technical', v: ev.technical_score },
                            { l: 'Complete', v: ev.completeness_score },
                            { l: 'Relevant', v: ev.relevance_score },
                            { l: 'Similarity', v: ev.semantic_similarity_score },
                            { l: 'Concepts', v: ev.concept_coverage_score },
                          ].map(s => (
                            <div key={s.l} className="bg-white border border-indigo-100/50 rounded-xl p-3 text-center shadow-sm">
                              <div className="text-[9px] font-extrabold text-slate-400 uppercase tracking-widest mb-1">{s.l}</div>
                              <div className={`text-lg font-black ${getScoreTextColor(s.v)}`}>{s.v}</div>
                            </div>
                          ))}
                        </div>
                        
                        {ev.feedback && (
                          <div className="text-sm text-slate-700 leading-relaxed border-t border-indigo-100/60 pt-5 mt-2">
                            <span className="font-extrabold text-slate-900 mr-2 uppercase tracking-wide text-[11px] bg-slate-100 px-2 py-1 rounded">Feedback</span>
                            <div className="mt-2 font-medium prose prose-sm prose-slate max-w-none prose-p:my-1 prose-pre:bg-slate-800 prose-pre:text-slate-100">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{ev.feedback}</ReactMarkdown>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="flex flex-wrap items-center gap-3 justify-center pt-2 pb-12">
        <Link to="/dashboard" className="btn btn-secondary shadow-sm px-6">Dashboard</Link>
        <Link to="/setup" className="btn btn-primary shadow-md px-6">New Interview</Link>
      </div>
    </div>
  );
}
