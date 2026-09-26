import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  BarChart3, Target, Lightbulb, Award, AlertCircle, Loader2, 
  Trophy, ClipboardList, TrendingUp, Calendar, BookOpen, CheckCircle2, FileText, ArrowRight
} from 'lucide-react';
import api from '../services/api';

export default function PerformanceDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { loadPerformance(); }, []);

  const loadPerformance = async () => {
    try {
      const res = await api.get('/users/performance');
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load performance data');
    } finally {
      setLoading(false);
    }
  };

  const getScoreTextColor = (score) => {
    if (score >= 80) return 'text-emerald-600';
    if (score >= 60) return 'text-amber-500';
    if (score >= 40) return 'text-orange-500';
    return 'text-red-500';
  };

  if (loading) {
    return (
      <div className="page-container max-w-6xl fade-up">
        <div className="page-header mb-8">
          <div className="h-8 w-64 bg-slate-200 rounded-lg animate-pulse mb-2"></div>
          <div className="h-4 w-96 bg-slate-100 rounded-md animate-pulse"></div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="card p-6 border-slate-100 shadow-sm flex items-center justify-between">
              <div className="space-y-2">
                <div className="h-4 w-24 bg-slate-100 rounded animate-pulse"></div>
                <div className="h-8 w-16 bg-slate-200 rounded-lg animate-pulse"></div>
              </div>
              <div className="w-12 h-12 rounded-xl bg-slate-100 animate-pulse"></div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 card p-6 h-64 bg-slate-50 animate-pulse border-slate-100"></div>
          <div className="card p-6 h-64 bg-slate-50 animate-pulse border-slate-100"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container max-w-lg mt-12 fade-up">
        <div className="card text-center p-10 bg-red-50/50 border-red-100">
          <AlertCircle size={40} className="text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-red-900 mb-2">Error</h2>
          <p className="text-red-700 mb-6 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!data?.has_data || !data.recent_interviews || data.recent_interviews.length === 0) {
    return (
      <div className="page-container max-w-4xl fade-up">
        <div className="page-header">
          <h1 className="page-title">Performance Analytics</h1>
          <p className="page-subtitle">Track your interview performance, identify trends, and get personalized recommendations.</p>
        </div>
        <div className="card text-center p-12 bg-slate-50/50 border-dashed">
          <div className="w-16 h-16 bg-white border border-slate-200 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-sm text-slate-400">
            <BarChart3 size={28} />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">No Completed Interviews Yet</h3>
          <p className="text-sm text-slate-500 mb-6 max-w-md mx-auto">
            Complete an interview to see your performance analytics, skill breakdowns, and personalized AI recommendations.
          </p>
          <Link to="/setup" className="btn btn-primary shadow-md">
            Start First Interview
          </Link>
        </div>
      </div>
    );
  }

  const { overall_average, skill_performance, bloom_performance, strengths, weak_areas, recommendations, recent_interviews } = data;
  const latestInterview = recent_interviews[0];

  const bloomColors = {
    'Remember': 'bg-indigo-400',
    'Understand': 'bg-emerald-400',
    'Apply': 'bg-amber-400',
    'Analyze': 'bg-orange-400',
    'Evaluate': 'bg-purple-400',
    'Create': 'bg-pink-400'
  };
  const bloomLevels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'];

  // Calculate SVG line chart points
  const svgWidth = Math.max(recent_interviews.length * 120, 800);
  const svgHeight = 220;
  const paddingX = 60;
  const paddingYTop = 40;
  const paddingYBottom = 40;
  const chartHeight = svgHeight - paddingYTop - paddingYBottom;
  
  const getX = (index) => {
    if (recent_interviews.length === 1) return svgWidth / 2;
    return paddingX + (index * ((svgWidth - 2 * paddingX) / (recent_interviews.length - 1)));
  };
  
  const getY = (score) => {
    return paddingYTop + chartHeight - ((score / 100) * chartHeight);
  };

  const points = recent_interviews.map((int, i) => `${getX(i)},${getY(int.average_score)}`).join(' ');

  return (
    <div className="page-container max-w-7xl fade-up">
      <div className="page-header">
        <h1 className="page-title">Performance Analytics</h1>
        <p className="page-subtitle">Track your interview performance, identify trends, and get personalized recommendations.</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="stat-card card-hover">
          <div className="flex items-center justify-between">
            <h3 className="eyebrow text-amber-500">Average Overall Score</h3>
            <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600"><Trophy size={16} /></div>
          </div>
          <div className="flex items-end gap-3 mt-1">
            <span className="text-3xl font-extrabold text-slate-900">{Math.round(overall_average)}%</span>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Across {recent_interviews.length} Int</span>
          </div>
        </div>
        
        <div className="stat-card card-hover">
          <div className="flex items-center justify-between">
            <h3 className="eyebrow text-indigo-500">Total Interviews</h3>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600"><ClipboardList size={16} /></div>
          </div>
          <div className="flex items-end gap-3 mt-1">
            <span className="text-3xl font-extrabold text-slate-900">{recent_interviews.length}</span>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Completed</span>
          </div>
        </div>

        <div className="stat-card card-hover">
          <div className="flex items-center justify-between">
            <h3 className="eyebrow text-emerald-500">Strong Skills</h3>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600"><CheckCircle2 size={16} /></div>
          </div>
          <div className="flex items-end gap-3 mt-1">
            <span className="text-3xl font-extrabold text-slate-900">{strengths.length}</span>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Top Tier</span>
          </div>
        </div>

        <div className="stat-card card-hover">
          <div className="flex items-center justify-between">
            <h3 className="eyebrow text-red-500">Areas to Improve</h3>
            <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center text-red-600"><TrendingUp size={16} /></div>
          </div>
          <div className="flex items-end gap-3 mt-1">
            <span className="text-3xl font-extrabold text-slate-900">{weak_areas.length}</span>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Practice</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        {/* Main Graph */}
        <div className="xl:col-span-2 card p-6 shadow-sm overflow-hidden flex flex-col">
          <div className="mb-6 border-b border-slate-100/60 pb-4">
            <h2 className="text-base font-bold text-slate-900">Performance Progress</h2>
            <p className="text-xs text-slate-500 mt-1">Your overall score across all completed interviews.</p>
          </div>
          <div className="flex-1 w-full overflow-x-auto scrollbar-hide border border-slate-100 rounded-xl bg-slate-50/50 shadow-inner">
            <svg width={svgWidth} height={svgHeight} className="min-w-full">
              {[0, 20, 40, 60, 80, 100].map(val => (
                <g key={val}>
                  <text x={30} y={getY(val) + 4} className="text-[10px] font-semibold fill-slate-400 text-end" textAnchor="end">{val}</text>
                  <line x1={40} y1={getY(val)} x2={svgWidth} y2={getY(val)} stroke="#e2e8f0" strokeDasharray="4 4" />
                </g>
              ))}
              
              {recent_interviews.length > 1 && (
                <polyline
                  points={points}
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="drop-shadow-[0_4px_4px_rgba(99,102,241,0.2)]"
                />
              )}
              
              {recent_interviews.map((int, i) => {
                const x = getX(i);
                const y = getY(int.average_score);
                const interviewNumber = recent_interviews.length - i;
                return (
                  <g key={int.id}>
                    <circle cx={x} cy={y} r="5" fill="#6366f1" stroke="#ffffff" strokeWidth="2" className="drop-shadow-sm" />
                    <text x={x} y={y - 12} className="text-xs font-extrabold fill-slate-900" textAnchor="middle">{Math.round(int.average_score)}%</text>
                    <text x={x} y={svgHeight - 15} className="text-[9px] font-bold fill-slate-400 uppercase tracking-wider" textAnchor="middle">Session {interviewNumber}</text>
                    {i === 0 && <text x={x} y={svgHeight - 4} className="text-[9px] font-extrabold fill-indigo-500 uppercase tracking-wider" textAnchor="middle">(Latest)</text>}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        {/* Skill-wise Performance */}
        <div className="card p-6 shadow-sm xl:col-span-1">
          <div className="mb-6 border-b border-slate-100/60 pb-4">
            <h2 className="text-base font-bold text-slate-900">Skill-wise Performance</h2>
            <p className="text-xs text-slate-500 mt-1">Your average scores in each skill area.</p>
          </div>
          {Object.keys(skill_performance).length > 0 ? (
            <div className="space-y-5">
              {Object.entries(skill_performance)
                .sort(([, a], [, b]) => b.average_score - a.average_score)
                .slice(0, 6)
                .map(([skill, perf], idx) => {
                  const colors = ['from-indigo-400 to-indigo-500', 'from-emerald-400 to-emerald-500', 'from-amber-400 to-amber-500', 'from-orange-400 to-orange-500', 'from-purple-400 to-purple-500', 'from-pink-400 to-pink-500'];
                  const bgGradient = colors[idx % colors.length];
                  return (
                    <div key={skill}>
                      <div className="flex justify-between items-end mb-2">
                        <span className="text-xs font-bold text-slate-700 truncate mr-2" title={skill}>{skill}</span>
                        <span className="text-xs font-black text-slate-900">{Math.round(perf.average_score)}%</span>
                      </div>
                      <div className="progress-track bg-slate-100">
                        <div 
                          className={`progress-fill bg-gradient-to-r ${bgGradient}`}
                          style={{ width: `${Math.min(100, perf.average_score)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No skill data available.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        {/* Bloom's Taxonomy */}
        <div className="card p-6 shadow-sm xl:col-span-1 flex flex-col">
          <div className="mb-6 border-b border-slate-100/60 pb-4">
            <h2 className="text-base font-bold text-slate-900">Bloom's Progression</h2>
            <p className="text-xs text-slate-500 mt-1">Your performance across cognitive levels.</p>
          </div>
          {bloom_performance && Object.keys(bloom_performance).length > 0 ? (
            <div className="flex-1 flex items-end justify-between min-h-[220px] pb-8 pt-4 relative pl-8 border-l border-b border-slate-100 bg-slate-50/30 rounded-bl-xl p-2">
              <div className="absolute left-[-24px] top-24 -rotate-90 text-[9px] font-extrabold text-slate-400 uppercase tracking-wider">Score %</div>
              
              <div className="flex justify-between items-end w-full h-full gap-2">
                {bloomLevels.map(level => {
                  const isZero = bloom_performance[level] === undefined;
                  const score = isZero ? 0 : bloom_performance[level];
                  
                  return (
                    <div key={level} className="flex flex-col items-center justify-end h-full flex-1 group">
                      <span className={`text-[10px] font-black mb-1.5 ${isZero ? 'text-slate-300' : 'text-slate-700'}`}>
                        {Math.round(score)}%
                      </span>
                      <div 
                        className={`w-full max-w-[28px] rounded-t-sm transition-all duration-1000 shadow-sm ${isZero ? 'bg-slate-200' : bloomColors[level]}`} 
                        style={{ height: `${Math.max(score, 2)}%` }}
                      ></div>
                      <div className="mt-2 text-center absolute -bottom-6 w-12 text-center" style={{ marginLeft: '-12px'}}>
                        <span className={`text-[9px] font-bold uppercase tracking-wider ${isZero ? 'text-slate-300' : 'text-slate-600'}`}>
                          {level.slice(0,3)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No Bloom data available yet.</p>
          )}
        </div>

        {/* Strengths and Weaknesses */}
        <div className="card p-6 shadow-sm xl:col-span-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 h-full">
            <div>
              <div className="flex items-center gap-2 mb-5 border-b border-slate-100/60 pb-4">
                <CheckCircle2 size={18} className="text-emerald-500" />
                <h2 className="text-base font-bold text-slate-900">Your Strengths</h2>
              </div>
              {strengths.length > 0 ? (
                <ul className="space-y-3">
                  {strengths.map(s => (
                    <li key={s} className="flex items-start gap-2.5 text-sm text-slate-700 font-medium">
                      <CheckCircle2 size={16} className="text-emerald-500 mt-0.5 shrink-0" />
                      <span>Proficient in <span className="font-bold text-slate-900">{s}</span></span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500 italic">Complete more interviews to identify strong areas.</p>
              )}
            </div>
            
            <div>
              <div className="flex items-center gap-2 mb-5 border-b border-slate-100/60 pb-4">
                <AlertCircle size={18} className="text-red-500" />
                <h2 className="text-base font-bold text-slate-900">Areas for Improvement</h2>
              </div>
              {weak_areas.length > 0 ? (
                <ul className="space-y-3">
                  {weak_areas.map(w => (
                    <li key={w} className="flex items-start gap-2.5 text-sm text-slate-700 font-medium">
                      <AlertCircle size={16} className="text-red-500 mt-0.5 shrink-0" />
                      <span>Needs review in <span className="font-bold text-slate-900">{w}</span></span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500 italic">No significant weak areas identified yet.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* AI Recommendations */}
      {recommendations.length > 0 && (
        <div className="card p-6 shadow-sm mb-6 border-t-4 border-t-purple-400">
          <div className="flex items-center gap-2 mb-5 border-b border-slate-100/60 pb-4">
            <Lightbulb size={18} className="text-purple-500" />
            <h2 className="text-base font-bold text-slate-900">AI Coaching Plan</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recommendations.map((rec, i) => (
              <div key={i} className="flex flex-col p-4 rounded-xl border border-slate-100 bg-slate-50/50 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <FileText size={14} className="text-purple-500" />
                  <span className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">Focus Area</span>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed font-medium">{rec.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Latest Interview Summary */}
      {latestInterview && (
        <div className="card p-6 shadow-sm border-l-4 border-l-indigo-500">
          <div className="flex items-center gap-2 mb-5 border-b border-slate-100/60 pb-4">
            <Calendar size={18} className="text-indigo-600" />
            <div>
              <h2 className="text-base font-bold text-slate-900">Latest Session Recap</h2>
            </div>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 p-5 bg-indigo-50/30 rounded-xl border border-indigo-100/50 items-center">
            <div className="col-span-2 md:col-span-1">
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mb-1">Session {recent_interviews.length}</div>
              <div className="text-xs font-bold text-slate-900">
                {latestInterview.date ? new Date(latestInterview.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Unknown Date'}
              </div>
            </div>
            
            <div className="col-span-1 md:col-span-1">
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mb-1">Score</div>
              <div className="text-2xl font-black text-slate-900 leading-none">
                {Math.round(latestInterview.average_score)}<span className="text-sm text-slate-400 ml-0.5">%</span>
              </div>
            </div>
            
            <div className="col-span-1 md:col-span-1">
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mb-1">Questions</div>
              <div className="text-lg font-bold text-slate-800 leading-none">
                {latestInterview.question_count}
              </div>
            </div>
            
            <div className="col-span-2">
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mb-2">Focus Areas</div>
              <div className="flex flex-wrap gap-1.5">
                {latestInterview.skills?.slice(0,3).map(s => (
                  <span key={s} className="badge badge-indigo bg-white text-[10px] truncate max-w-[80px]" title={s}>{s}</span>
                )) || <span className="text-xs font-medium text-slate-500">General</span>}
              </div>
            </div>
            
            <div className="col-span-2 md:col-span-1 text-right mt-2 md:mt-0">
              <Link to={`/results/${latestInterview.id}`} className="btn btn-primary text-xs w-full justify-center">
                Review &rarr;
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
