import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { Play, Settings, AlertCircle, ArrowRight, Briefcase, FileText } from 'lucide-react';

export default function InterviewSetup() {
  const [resume, setResume] = useState(null);
  const [hasJD, setHasJD] = useState(false);
  const [targetSkills, setTargetSkills] = useState([]);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      api.get('/resumes/current'),
      api.get('/job-descriptions/current').catch(() => null),
      api.get('/job-descriptions/mapping').catch(() => null),
    ])
      .then(([res, jdRes, mapRes]) => {
        setResume(res.data);
        setHasJD(!!jdRes?.data);
        const skills = mapRes?.data?.interview_skills?.length > 0
          ? mapRes.data.interview_skills
          : (res.data.skills || []);
        setTargetSkills(skills);
        setSelectedSkills(skills);
      })
      .catch(() => setError('Please upload a resume first'))
      .finally(() => setLoading(false));
  }, []);

  const toggleSkill = (skill) => {
    setSelectedSkills(prev =>
      prev.includes(skill) ? prev.filter(s => s !== skill) : [...prev, skill]
    );
  };

  const handleStart = async () => {
    if (!resume) { setError('Please upload a resume first'); return; }
    if (selectedSkills.length === 0) { setError('Select at least one skill'); return; }

    setError('');
    setStarting(true);
    try {
      const res = await api.post('/interviews/start', {
        resume_id: resume.id,
        difficulty: null,
        question_type: null,
        question_count: null,
        selected_skills: selectedSkills,
      });
      navigate(`/interview/${res.data.session_id || res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start interview');
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="page-container max-w-lg mt-12 fade-up">
        <div className="card text-center p-10 bg-gradient-to-b from-white to-amber-50/30 border-amber-100">
          <div className="w-16 h-16 bg-amber-100 text-amber-500 rounded-full flex items-center justify-center mx-auto mb-5 shadow-sm">
            <FileText size={28} />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2.5">No Resume Uploaded</h2>
          <p className="text-slate-500 mb-8 text-sm leading-relaxed">
            You need to upload your resume before starting an interview. The AI uses this to build a tailored profile and generate personalized technical questions.
          </p>
          <button onClick={() => navigate('/resume')} className="btn btn-primary w-full shadow-md">
            Upload Resume
          </button>
        </div>
      </div>
    );
  }

  if (!hasJD) {
    return (
      <div className="page-container max-w-lg mt-12 fade-up">
        <div className="card text-center p-10 bg-gradient-to-b from-white to-blue-50/30 border-blue-100">
          <div className="w-16 h-16 bg-blue-100 text-blue-500 rounded-full flex items-center justify-center mx-auto mb-5 shadow-sm">
            <Briefcase size={28} />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2.5">Missing Job Description</h2>
          <p className="text-slate-500 mb-8 text-sm leading-relaxed">
            The adaptive interview engine targets skills based on the gap between your resume and a target role. Please upload a JD so we can focus on what matters.
          </p>
          <button onClick={() => navigate('/resume')} className="btn btn-primary w-full shadow-md bg-blue-600 hover:bg-blue-700">
            Upload Job Description
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container max-w-3xl fade-up">
      <div className="page-header">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
            <Settings size={20} />
          </div>
          <h1 className="page-title">Interview Configuration</h1>
        </div>
        <p className="page-subtitle ml-13">
          Select the skills you want the adaptive engine to evaluate. The AI will dynamically adjust difficulty and question types as you progress.
        </p>
      </div>

      {error && (
        <div className="error-banner mb-6 shadow-sm">
          <AlertCircle size={16} className="flex-shrink-0" />
          {error}
        </div>
      )}

      <div className="card p-6 sm:p-8 mb-6 shadow-sm">
        <div className="flex items-center justify-between mb-5 pb-5 border-b border-slate-100/60">
          <div>
            <h2 className="text-base font-bold text-slate-900">Target Skills</h2>
            <p className="text-xs text-slate-500 mt-1">{selectedSkills.length} of {targetSkills.length} selected for evaluation</p>
          </div>
          <button
            className="btn btn-ghost text-indigo-600 text-xs px-3 py-1.5"
            onClick={() => setSelectedSkills(selectedSkills.length === targetSkills.length ? [] : [...targetSkills])}
          >
            {selectedSkills.length === targetSkills.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>
        
        <div className="flex flex-wrap gap-2.5">
          {targetSkills.map(s => {
            const isSelected = selectedSkills.includes(s);
            return (
              <button
                key={s}
                onClick={() => toggleSkill(s)}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-full cursor-pointer transition-all duration-200 border ${
                  isSelected
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50'
                }`}
              >
                {s}
              </button>
            );
          })}
        </div>
      </div>

      {/* Start Action */}
      <div className="flex flex-col items-center max-w-sm mx-auto">
        <button
          onClick={handleStart}
          disabled={starting || selectedSkills.length === 0}
          className="btn btn-primary w-full py-3.5 text-base shadow-md group relative overflow-hidden"
        >
          {starting ? (
            <>
              <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin mr-2"></div>
              Initializing Adaptive Engine...
            </>
          ) : (
            <>
              <Play size={18} className="fill-current mr-1" />
              <span className="font-bold tracking-wide">Start Interview</span>
              <ArrowRight size={16} className="absolute right-5 opacity-0 group-hover:opacity-100 transform -translate-x-2 group-hover:translate-x-0 transition-all duration-300" />
            </>
          )}
        </button>
        
        <p className="text-xs text-slate-400 mt-4 font-medium flex items-center justify-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></span>
          The interview continues until you choose to finish.
        </p>
      </div>
    </div>
  );
}
