import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { Upload, FileText, Trash2, Check, UploadCloud, ChevronRight, Briefcase } from 'lucide-react';

export default function ResumeUpload() {
  const [resume, setResume] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobDescription, setJobDescription] = useState(null);
  const [jdUploading, setJdUploading] = useState(false);
  const [skillMapping, setSkillMapping] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const fileRef = useRef(null);
  const jdFileRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      api.get('/resumes/current').then(res => setResume(res.data)).catch(() => {}),
      api.get('/job-descriptions/current').then(res => setJobDescription(res.data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (resume && jobDescription) {
      api.get('/job-descriptions/mapping')
        .then(res => setSkillMapping(res.data))
        .catch(() => setSkillMapping(null));
    } else {
      setSkillMapping(null);
    }
  }, [resume?.id, jobDescription?.id]);

  const handleUpload = async (e) => {
    const file = e.target?.files?.[0] || e.dataTransfer?.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Resume: Only PDF files are accepted');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Resume: File too large (max 5MB)');
      return;
    }

    setError('');
    setUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/resumes/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResume(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Resume upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    if (!resume) return;
    try {
      await api.delete(`/resumes/${resume.id}`);
      setResume(null);
    } catch {
      setError('Failed to delete resume');
    }
  };

  const handleJdUpload = async (e) => {
    const file = e.target?.files?.[0] || e.dataTransfer?.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Job Description: Only PDF files are accepted');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Job Description: File too large (max 5MB)');
      return;
    }

    setError('');
    setJdUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/job-descriptions/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setJobDescription(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Job Description upload failed');
    } finally {
      setJdUploading(false);
      if (jdFileRef.current) jdFileRef.current.value = '';
    }
  };

  const handleJdDelete = async () => {
    if (!jobDescription) return;
    try {
      await api.delete(`/job-descriptions/${jobDescription.id}`);
      setJobDescription(null);
    } catch {
      setError('Failed to delete job description');
    }
  };

  const categorizeSkills = (skills) => {
    const categories = {
      'CORE LANGUAGES': ['java', 'python', 'c++', 'c#', 'typescript', 'javascript', 'sql', 'html', 'css', 'go', 'ruby'],
      'WEB & FRAMEWORKS': ['react', 'node', 'flask', 'next', 'tailwind', 'django', 'spring', 'express', 'vue', 'angular'],
      'DATABASES & SYSTEMS': ['postgres', 'redis', 'prisma', 'kafka', 'rest', 'mongodb', 'mysql', 'api'],
      'DEVOPS & TESTING': ['docker', 'aws', 'junit', 'git', 'jest', 'cypress', 'kubernetes', 'gcp', 'azure', 'ci/cd']
    };

    const result = {
      'CORE LANGUAGES': [],
      'WEB & FRAMEWORKS': [],
      'DATABASES & SYSTEMS': [],
      'DEVOPS & TESTING': [],
      'OTHER COMPETENCIES': []
    };

    if (!skills) return result;

    skills.forEach(skill => {
      const s = skill.toLowerCase();
      let matched = false;
      for (const [cat, keywords] of Object.entries(categories)) {
        if (keywords.some(k => s.includes(k))) {
          result[cat].push(skill);
          matched = true;
          break;
        }
      }
      if (!matched) result['OTHER COMPETENCIES'].push(skill);
    });

    return result;
  };

  if (loading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const groupedSkills = categorizeSkills(resume?.skills);

  return (
    <div className="page-container max-w-5xl fade-up">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 page-header">
        <div>
          <div className="badge badge-indigo mb-3 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 mr-1.5 animate-pulse"></span>
            Intelligence Engine
          </div>
          <h1 className="page-title">Resume & Skills</h1>
          <p className="page-subtitle">Upload both your Resume and target Job Description to generate highly targeted interview scenarios.</p>
        </div>
        
        {resume && (
          <div className="mt-5 md:mt-0 flex flex-col md:items-end gap-3">
            <div className="badge badge-emerald shadow-sm px-3 py-1.5">
              <Check size={14} className="mr-1" /> Active Parsing v2.4
            </div>
            {jobDescription ? (
              <button onClick={() => navigate('/setup')} className="btn btn-primary shadow-sm text-sm py-2">
                Continue to Setup <ChevronRight size={16} className="ml-1" />
              </button>
            ) : (
              <span className="badge badge-amber shadow-sm px-3 py-1.5">
                Upload Job Description to unlock targeted mode
              </span>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="error-banner mb-6 shadow-sm">
          {error}
        </div>
      )}

      {/* 50/50 Equal Split Container */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        
        {/* LEFT: Resume */}
        <div className="flex flex-col">
          <div className="text-sm font-bold text-slate-800 mb-2.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5"><FileText size={16} className="text-indigo-600" /> Resume Profile</span>
            {resume && <span className="badge badge-emerald py-0.5 text-[10px]">Uploaded</span>}
          </div>

          {!resume ? (
            <label
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); handleUpload(e); }}
              className="flex flex-col items-center justify-center w-full h-[300px] border-2 border-dashed border-slate-300 rounded-2xl bg-white hover:bg-indigo-50/50 hover:border-indigo-300 transition-colors cursor-pointer relative overflow-hidden group shadow-sm"
            >
              <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
              {uploading ? (
                <div className="flex flex-col items-center">
                  <div className="animate-spin-slow rounded-full h-12 w-12 border-b-2 border-t-2 border-indigo-600 mb-4"></div>
                  <p className="text-sm font-bold text-slate-900">Parsing PDF...</p>
                </div>
              ) : (
                <div className="flex flex-col items-center text-center p-6">
                  <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-indigo-100 group-hover:text-indigo-600 text-slate-400 transition-colors">
                    <UploadCloud size={32} />
                  </div>
                  <p className="text-base font-bold text-slate-900 mb-1">Upload Resume</p>
                  <p className="text-xs text-slate-500 mb-5">PDF up to 5MB</p>
                  <div className="btn btn-secondary text-xs pointer-events-none shadow-sm">Browse Files</div>
                </div>
              )}
            </label>
          ) : (
            <div className="card h-[300px] flex flex-col justify-between p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 flex-shrink-0 border border-indigo-100">
                  <FileText size={24} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-bold text-slate-900 text-base truncate" title={resume.filename || 'Resume.pdf'}>
                      {resume.filename || 'Resume.pdf'}
                    </span>
                  </div>
                  <div className="text-sm text-slate-500 space-y-1.5 font-medium">
                    {resume.name && <div className="text-slate-800">Candidate: {resume.name}</div>}
                    <div>{resume.page_count || 1} page{resume.page_count === 1 ? '' : 's'}</div>
                    <div>Parsed {resume.uploaded_at ? new Date(resume.uploaded_at).toLocaleDateString() : new Date().toLocaleDateString()}</div>
                    <div className="text-indigo-600 font-bold">{resume.skills?.length || 0} skills detected</div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                <label className="btn btn-secondary cursor-pointer flex-1 text-xs justify-center">
                  <Upload size={14} className="mr-1.5" /> Replace
                  <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleUpload} disabled={uploading} />
                </label>
                <button
                  onClick={handleDelete}
                  className="btn btn-danger flex-1 text-xs justify-center shadow-sm"
                >
                  <Trash2 size={14} className="mr-1.5" /> Delete
                </button>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Job Description */}
        <div className="flex flex-col">
          <div className="text-sm font-bold text-slate-800 mb-2.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5"><Briefcase size={16} className="text-blue-600" /> Target Role (Optional)</span>
            {jobDescription && <span className="badge badge-emerald py-0.5 text-[10px]">Uploaded</span>}
          </div>

          {!jobDescription ? (
            <label
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); handleJdUpload(e); }}
              className="flex flex-col items-center justify-center w-full h-[300px] border-2 border-dashed border-slate-300 rounded-2xl bg-white hover:bg-blue-50/50 hover:border-blue-300 transition-colors cursor-pointer relative overflow-hidden group shadow-sm"
            >
              <input ref={jdFileRef} type="file" accept=".pdf" className="hidden" onChange={handleJdUpload} disabled={jdUploading} />
              {jdUploading ? (
                <div className="flex flex-col items-center">
                  <div className="animate-spin-slow rounded-full h-12 w-12 border-b-2 border-t-2 border-blue-600 mb-4"></div>
                  <p className="text-sm font-bold text-slate-900">Parsing PDF...</p>
                </div>
              ) : (
                <div className="flex flex-col items-center text-center p-6">
                  <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-blue-100 group-hover:text-blue-600 text-slate-400 transition-colors">
                    <Briefcase size={32} />
                  </div>
                  <p className="text-base font-bold text-slate-900 mb-1">Upload Job Description</p>
                  <p className="text-xs text-slate-500 mb-5">PDF up to 5MB</p>
                  <div className="btn btn-secondary text-xs pointer-events-none shadow-sm">Browse Files</div>
                </div>
              )}
            </label>
          ) : (
            <div className="card h-[300px] flex flex-col justify-between p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 flex-shrink-0 border border-blue-100">
                  <Briefcase size={24} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="font-bold text-slate-900 text-base truncate" title={jobDescription.filename || 'JobDescription.pdf'}>
                      {jobDescription.filename || 'JobDescription.pdf'}
                    </span>
                  </div>
                  <div className="text-sm text-slate-500 space-y-1.5 font-medium">
                    <div>{jobDescription.page_count || 1} page{jobDescription.page_count === 1 ? '' : 's'}</div>
                    <div>Parsed {jobDescription.uploaded_at ? new Date(jobDescription.uploaded_at).toLocaleDateString() : new Date().toLocaleDateString()}</div>
                    <div className="text-blue-600 font-bold">{jobDescription.skills?.length || 0} requirements</div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                <label className="btn btn-secondary cursor-pointer flex-1 text-xs justify-center">
                  <Upload size={14} className="mr-1.5" /> Replace
                  <input ref={jdFileRef} type="file" accept=".pdf" className="hidden" onChange={handleJdUpload} disabled={jdUploading} />
                </label>
                <button
                  onClick={handleJdDelete}
                  className="btn btn-danger flex-1 text-xs justify-center shadow-sm"
                >
                  <Trash2 size={14} className="mr-1.5" /> Delete
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Role Alignment & Skill Mapping */}
      {resume && jobDescription && skillMapping && (
        <div className="card p-6 border-indigo-100 bg-gradient-to-br from-white to-indigo-50/20 mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-100/60">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900 tracking-tight">Role Alignment & Mapping</h2>
                <span className="badge badge-indigo text-[10px]">Targeted Plan</span>
              </div>
              <p className="text-sm text-slate-500 mt-1">Comparison between your resume competencies and job requirements</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="badge badge-emerald">{skillMapping.matched_skills?.length || 0} Matched</span>
              <span className="badge badge-amber">{skillMapping.gap_skills?.length || 0} Gaps</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="card border-emerald-100 bg-emerald-50/30 p-5">
              <div className="eyebrow text-emerald-800 mb-3 flex items-center gap-1.5">
                <Check size={14} className="text-emerald-600" /> Matched Skills
              </div>
              {skillMapping.matched_skills && skillMapping.matched_skills.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {skillMapping.matched_skills.map(s => (
                    <span key={s} className="badge badge-emerald bg-white text-xs">{s}</span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No direct skill overlap detected.</p>
              )}
            </div>

            <div className="card border-amber-100 bg-amber-50/30 p-5">
              <div className="eyebrow text-amber-800 mb-3 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Target Gaps
              </div>
              {skillMapping.gap_skills && skillMapping.gap_skills.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {skillMapping.gap_skills.map(s => (
                    <span key={s} className="badge badge-amber bg-white text-xs">{s}</span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No skill gaps found.</p>
              )}
            </div>
          </div>

          {skillMapping.resume_only && skillMapping.resume_only.length > 0 && (
            <div className="mt-5 pt-4 border-t border-slate-100/60">
              <div className="eyebrow text-slate-500 mb-3">Additional Resume Competencies ({skillMapping.resume_only.length})</div>
              <div className="flex flex-wrap gap-1.5">
                {skillMapping.resume_only.map(s => (
                  <span key={s} className="badge badge-slate bg-white text-xs">{s}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Extracted Details for Resume */}
      {resume && (
        <div className="space-y-6">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100/60">
              <div>
                <h2 className="text-base font-bold text-slate-900 tracking-tight">Extracted Competencies</h2>
                <p className="text-xs text-slate-500 mt-1">Categorized for interview question weighting</p>
              </div>
              <div className="badge badge-slate shadow-sm">{resume.skills?.length || 0} Detected</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {Object.entries(groupedSkills).map(([category, skills]) => {
                if (skills.length === 0) return null;
                
                let badgeClass = "badge-indigo";
                if (category === 'DATABASES & SYSTEMS') badgeClass = "badge-emerald";
                else if (category === 'DEVOPS & TESTING') badgeClass = "badge-amber";
                else if (category === 'OTHER COMPETENCIES') badgeClass = "badge-slate";

                return (
                  <div key={category} className="border border-slate-100 bg-slate-50/50 rounded-xl p-5">
                    <div className="eyebrow text-slate-500 mb-3">{category}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {skills.map(s => (
                        <span key={s} className={`badge ${badgeClass} bg-white text-xs shadow-sm`}>{s}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {resume.projects && resume.projects.length > 0 && (
            <div className="card p-6">
              <div className="mb-6 pb-4 border-b border-slate-100/60">
                <h2 className="text-base font-bold text-slate-900 tracking-tight">Key Engineering Projects</h2>
                <p className="text-xs text-slate-500 mt-1">Highlighted projects used to formulate architecture questions</p>
              </div>
              
              <div className="space-y-4">
                {resume.projects.map((p, i) => (
                  <div key={i} className="border border-slate-200 rounded-xl p-5 bg-slate-50/30">
                    <h3 className="text-sm font-bold text-slate-900 mb-2">{p.name || `Project ${i + 1}`}</h3>
                    <p className="text-sm text-slate-600 mb-4 leading-relaxed font-medium">{p.description}</p>
                    {p.technologies && p.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {p.technologies.map(t => (
                          <span key={t} className="badge badge-slate bg-white shadow-sm text-xs">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {resume.experience && resume.experience.length > 0 && (
            <div className="card p-6">
              <div className="mb-6 pb-4 border-b border-slate-100/60">
                <h2 className="text-base font-bold text-slate-900 tracking-tight">Experience & Career History</h2>
              </div>
              <div className="space-y-6">
                {resume.experience.map((exp, i) => (
                  <div key={i} className="relative pl-6 border-l-2 border-indigo-100 pb-2 last:pb-0 last:border-transparent">
                    <div className="absolute w-3 h-3 bg-indigo-600 rounded-full -left-[7px] top-1.5 ring-4 ring-white shadow-sm"></div>
                    <div className="mb-2">
                      <h3 className="text-sm font-bold text-slate-900">{exp.role}</h3>
                    </div>
                    {exp.description && (
                      <ul className="mt-2 space-y-2 list-disc list-outside ml-4 text-sm text-slate-600 font-medium leading-relaxed">
                        {exp.description.split('.').filter(Boolean).map((sentence, idx) => (
                          <li key={idx} className="pl-1">{sentence.trim()}.</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
