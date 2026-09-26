import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import {
  Zap, FileText, CheckCircle2, HelpCircle, TrendingUp,
  ChevronRight, BarChart3, AlertCircle, Clock, ArrowRight, Play
} from 'lucide-react';

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [resume, setResume] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [statsRes, historyRes] = await Promise.all([
          api.get('/users/stats'),
          api.get('/interviews/history'),
        ]);
        setStats(statsRes.data);
        setHistory(historyRes.data.slice(0, 5));
        try {
          const resumeRes = await api.get('/resumes/current');
          setResume(resumeRes.data);
        } catch { /* no resume yet */ }
      } catch (err) {
        console.error('Failed to load dashboard:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const getPerformanceStage = (score) => {
    if (!score) return { title: "Getting Started", desc: "Complete your first interview to establish a baseline.", polish: "Needs Polish" };
    if (score >= 80) return { title: "Advanced Stage", desc: "Consistently scoring high. Ready for complex system design.", polish: "Excellent" };
    if (score >= 60) return { title: "Intermediate Stage", desc: "Solid foundation, with room to grow in problem efficiency.", polish: "On Track" };
    return { title: "Foundation Stage", desc: "Building core competencies. Focus on foundational concepts.", polish: "Needs Polish" };
  };

  const perfStage = getPerformanceStage(stats?.average_score);

  return (
    <div className="flex flex-col min-h-screen bg-slate-50">
      {/* Top Header */}
      <header className="h-16 glass-header border-b border-slate-200/60 px-8 flex items-center justify-between sticky top-0 z-40">
        <div className="text-sm font-semibold text-slate-700 hidden sm:block">Overview</div>
        <div className="flex items-center gap-4 ml-auto">
          <Link to={resume ? '/setup' : '/resume'} className="btn btn-primary text-xs py-1.5 px-4 shadow-sm">
            <Play size={14} className="fill-current" /> New Interview
          </Link>
        </div>
      </header>

      {/* Main Dashboard Content */}
      <main className="flex-1 p-4 sm:p-8 max-w-7xl mx-auto w-full space-y-6 sm:space-y-8 fade-up">

        {/* Welcome Banner */}
        <div className="card p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 border-indigo-100/50 bg-gradient-to-br from-white to-indigo-50/20">
          <div className="max-w-2xl">
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
              Welcome back, <span className="text-indigo-600">{user?.name?.split(' ')[0] || 'User'}</span>
              <span className="badge badge-emerald hidden sm:inline-flex px-3 py-1 ml-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-[pulse-dot_2s_ease-in-out_infinite]"></div>
                AI Coach Ready
              </span>
            </h1>
            <p className="text-slate-500 mt-2.5 text-sm sm:text-base leading-relaxed">
              Ready for your next mock interview session? We generate personalized questions based on your resume and recent scoring trends.
            </p>
            <div className="flex flex-wrap items-center gap-4 mt-5 text-sm text-slate-600 font-medium">
              <span className="flex items-center gap-1.5"><Zap size={16} className="text-amber-500 fill-amber-500/20" /> Quick prep: ~15 mins</span>
              <span className="text-slate-300 hidden sm:inline">•</span>
              <span className="flex items-center gap-1.5">
                <FileText size={16} className="text-indigo-500" />
                Focus area: {resume?.skills?.[0] || 'Core Concepts'}
              </span>
            </div>
          </div>
          <div className="flex-shrink-0">
            <Link to={resume ? '/setup' : '/resume'} className="btn btn-primary w-full md:w-auto px-6 py-3 text-sm">
              <Play size={16} className="fill-current" /> Start Practice
            </Link>
          </div>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 fade-up-delay-1">
          <div className="stat-card card-hover group">
            <div className="flex items-center justify-between">
              <h3 className="eyebrow text-slate-500 group-hover:text-indigo-500 transition-colors">Total Interviews</h3>
              <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600"><FileText size={16} /></div>
            </div>
            <div className="flex items-end gap-3 mt-1">
              <span className="text-3xl font-extrabold text-slate-900">{stats?.total_interviews || 0}</span>
              {stats?.total_interviews > 0 && <span className="badge badge-emerald mb-1">+{stats.total_interviews} total</span>}
            </div>
          </div>

          <div className="stat-card card-hover group">
            <div className="flex items-center justify-between">
              <h3 className="eyebrow text-slate-500 group-hover:text-emerald-500 transition-colors">Completed</h3>
              <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600"><CheckCircle2 size={16} /></div>
            </div>
            <div className="flex items-end gap-3 mt-1">
              <span className="text-3xl font-extrabold text-slate-900">{stats?.completed_interviews || 0}</span>
              {stats?.total_interviews > 0 && (
                <span className="badge badge-emerald mb-1">{Math.round((stats.completed_interviews / stats.total_interviews) * 100)}%</span>
              )}
            </div>
          </div>

          <div className="stat-card card-hover group">
            <div className="flex items-center justify-between">
              <h3 className="eyebrow text-slate-500 group-hover:text-amber-500 transition-colors">Questions Practiced</h3>
              <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600"><HelpCircle size={16} /></div>
            </div>
            <div className="flex items-end gap-3 mt-1">
              <span className="text-3xl font-extrabold text-slate-900">{stats?.total_questions || 0}</span>
              {stats?.total_questions > 0 && <span className="badge badge-amber mb-1">AI Evaluated</span>}
            </div>
          </div>

          <div className="stat-card card-hover group">
            <div className="flex items-center justify-between">
              <h3 className="eyebrow text-slate-500 group-hover:text-purple-500 transition-colors">Answered In Depth</h3>
              <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600"><TrendingUp size={16} /></div>
            </div>
            <div className="flex items-end gap-3 mt-1">
              <span className="text-3xl font-extrabold text-slate-900">{stats?.total_answered || 0}</span>
            </div>
          </div>
        </div>

        {/* 2-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start fade-up-delay-2">
          
          {/* Left Column */}
          <div className="lg:col-span-5 space-y-6">
            
            {/* Overall Performance Card */}
            <div className="card overflow-hidden flex flex-col">
              <div className="p-5 border-b border-slate-100/60 flex items-center justify-between bg-slate-50/50">
                <div className="flex items-center gap-2.5">
                  <BarChart3 size={16} className="text-indigo-600" />
                  <h2 className="text-sm font-bold text-slate-900">Overall Performance</h2>
                </div>
                <span className="badge badge-amber">{perfStage.polish}</span>
              </div>
              
              <div className="p-6">
                <div className="flex items-start gap-5 mb-8">
                  <div className="text-center">
                    <div className="text-4xl font-extrabold tracking-tight text-slate-900">
                      {stats?.average_score != null ? Math.round(stats.average_score) : 0}<span className="text-xl text-slate-400">%</span>
                    </div>
                    <div className="eyebrow mt-1 text-[10px]">Avg Score</div>
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 mb-1">{perfStage.title}</h4>
                    <p className="text-xs text-slate-500 leading-relaxed font-medium">{perfStage.desc}</p>
                  </div>
                </div>

                <div className="space-y-2 mb-6">
                  <div className="flex justify-between text-xs font-semibold text-slate-700">
                    <span>Overall Mastery</span>
                    <span>{stats?.average_score != null ? Math.round(stats.average_score) : 0}%</span>
                  </div>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${stats?.average_score || 0}%` }}></div>
                  </div>
                </div>

                <div className="info-banner bg-indigo-50/50 border-indigo-100/50">
                  <AlertCircle size={16} className="text-indigo-500 flex-shrink-0" />
                  <div className="flex-1">
                    <span className="font-semibold block mb-0.5">Recommended AI Target:</span>
                    <span className="text-indigo-700/80 leading-snug">Focus on {resume?.skills?.[0] || 'core technical'} concepts to push your average score past 60%.</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Resume Card */}
            <div className="card overflow-hidden">
              <div className="p-5 border-b border-slate-100/60 flex items-center justify-between bg-slate-50/50">
                <div className="flex items-center gap-2.5">
                  <FileText size={16} className="text-indigo-600" />
                  <h2 className="text-sm font-bold text-slate-900">Active Profile</h2>
                </div>
                <Link to="/resume" className="text-xs font-bold text-indigo-600 hover:text-indigo-700 no-underline">Manage</Link>
              </div>
              
              <div className="p-6">
                {!resume ? (
                  <div className="empty-state py-8">
                    <p className="text-sm text-slate-500 mb-4 font-medium">No resume uploaded yet.</p>
                    <Link to="/resume" className="btn btn-secondary text-xs w-full">Upload Resume</Link>
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col gap-1 mb-5">
                      <span className="text-sm font-bold text-slate-900 truncate">{resume.filename || 'resume.pdf'}</span>
                      <span className="text-xs text-slate-500">Updated {new Date(resume.created_at).toLocaleDateString()}</span>
                    </div>
                    
                    <div className="eyebrow mb-2.5">Identified Skills ({resume.skills?.length || 0})</div>
                    <div className="flex flex-wrap gap-1.5 mb-5">
                      {(resume.skills || []).slice(0, 6).map(s => (
                        <span key={s} className="badge badge-slate">{s}</span>
                      ))}
                      {(resume.skills || []).length > 6 && (
                        <span className="badge badge-slate bg-transparent border-dashed">+{ (resume.skills || []).length - 6 } more</span>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
            
          </div>

          {/* Right Column */}
          <div className="lg:col-span-7">
            
            {/* Recent Sessions Card */}
            <div className="card overflow-hidden flex flex-col h-full">
              <div className="p-5 border-b border-slate-100/60 flex items-center justify-between bg-slate-50/50">
                <div className="flex items-center gap-2.5">
                  <Clock size={16} className="text-indigo-600" />
                  <h2 className="text-sm font-bold text-slate-900">Recent Sessions</h2>
                </div>
                {history.length > 0 && (
                  <Link to="/history" className="text-xs font-bold text-indigo-600 flex items-center gap-1 hover:text-indigo-700 no-underline">
                    View all <ArrowRight size={14} />
                  </Link>
                )}
              </div>

              <div className="flex-1">
                {history.length === 0 ? (
                  <div className="empty-state py-16">
                    <div className="empty-state-icon"><Clock size={20} /></div>
                    <h4 className="text-sm font-bold text-slate-900 mb-1">No sessions yet</h4>
                    <p className="text-xs text-slate-500 font-medium max-w-xs">Complete your first interview to see performance analytics here.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100/80">
                    {history.map((h, i) => (
                      <Link 
                        to={h.status === 'completed' ? `/results/${h.id}` : `/interview/${h.id}`} 
                        key={h.id} 
                        className="p-5 flex items-center justify-between gap-4 hover:bg-slate-50 transition-colors no-underline group"
                      >
                        <div className="flex items-center gap-4 min-w-0">
                          <div className="w-10 h-10 rounded-lg bg-slate-100/80 text-slate-500 text-xs font-bold flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
                            #{history.length - i}
                          </div>
                          <div className="min-w-0">
                            <h4 className="text-sm font-bold text-slate-900 mb-1 truncate">{h.selected_skills?.[0] || 'Technical'} Practice</h4>
                            <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                              <span className="capitalize">{h.difficulty}</span>
                              <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                              <span>{h.questions_answered} answered</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-5 flex-shrink-0">
                          <div className="text-right">
                            {h.average_score != null ? (
                              <>
                                <div className={`text-lg font-bold ${h.average_score >= 70 ? 'text-emerald-600' : h.average_score >= 50 ? 'text-amber-500' : 'text-red-500'}`}>
                                  {Math.round(h.average_score)}%
                                </div>
                              </>
                            ) : (
                              <span className="badge badge-amber text-[10px]">In Progress</span>
                            )}
                          </div>
                          <ChevronRight size={16} className="text-slate-300 group-hover:text-indigo-500 transition-colors hidden sm:block" />
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}
