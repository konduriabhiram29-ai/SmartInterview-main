import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import { User, Mail, Calendar, FileText, CheckCircle2, HelpCircle, Edit3, Save, X, Activity, UserCog } from 'lucide-react';

export default function Profile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get('/users/profile')
      .then(res => {
        setProfile(res.data);
        setName(res.data.user.name);
      })
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.put('/users/profile', { name: name.trim() });
      setProfile(prev => ({ ...prev, user: { ...prev.user, name: name.trim() } }));
      setEditing(false);
    } catch {
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin-slow rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  const u = profile?.user;
  const stats = profile?.stats;
  const resume = profile?.resume;

  return (
    <div className="page-container max-w-4xl fade-up">
      <div className="page-header flex items-center gap-4 mb-8">
        <div className="w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shadow-sm">
          <UserCog size={28} />
        </div>
        <div>
          <h1 className="page-title mb-1">Account Profile</h1>
          <p className="page-subtitle max-w-2xl">
            Manage your personal information and view your global activity stats.
          </p>
        </div>
      </div>

      {/* User Info */}
      <div className="card p-8 mb-8 border border-slate-100/80 shadow-sm relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-50/50 rounded-full blur-3xl -mr-20 -mt-20 group-hover:bg-indigo-100/50 transition-colors pointer-events-none"></div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 relative z-10">
          <div className="flex items-center gap-6">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg flex items-center justify-center flex-shrink-0 border-4 border-white">
              <User size={40} />
            </div>
            <div>
              {editing ? (
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
                  <input 
                    className="input py-2 px-4 font-bold text-lg max-w-[240px] shadow-sm bg-white" 
                    value={name} 
                    onChange={e => setName(e.target.value)} 
                    autoFocus 
                  />
                  <div className="flex items-center gap-2">
                    <button onClick={handleSave} className="btn btn-primary py-2 px-4 shadow-sm" disabled={saving}>
                      {saving ? 'Saving...' : <><Save size={16} className="mr-1.5" /> Save</>}
                    </button>
                    <button onClick={() => { setEditing(false); setName(u.name); }} className="btn btn-secondary py-2 px-4">
                      <X size={16} className="mr-1.5" /> Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-3xl font-black text-slate-900 mb-1.5 tracking-tight">{u?.name}</div>
              )}
              
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center text-sm text-slate-500 font-medium">
                  <Mail size={14} className="mr-2 text-indigo-400" />
                  {u?.email}
                </div>
                
                {u?.created_at && (
                  <div className="flex items-center text-sm text-slate-500 font-medium">
                    <Calendar size={14} className="mr-2 text-indigo-400" />
                    Joined {new Date(u.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {!editing && (
            <button onClick={() => setEditing(true)} className="btn btn-secondary shadow-sm text-sm px-5 py-2.5 mt-2 sm:mt-0 flex-shrink-0 hover:bg-slate-50">
              <Edit3 size={16} className="mr-2 text-slate-500" /> Edit Profile
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Stats */}
        <div className="card p-6 shadow-sm flex flex-col border border-slate-100">
          <div className="flex items-center gap-2 mb-6 border-b border-slate-100/60 pb-4">
            <Activity size={18} className="text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Activity Overview</h2>
          </div>
          
          <div className="grid grid-cols-2 gap-4 flex-1">
            <div className="bg-slate-50/50 rounded-2xl p-5 border border-slate-100 flex flex-col items-center justify-center text-center shadow-sm">
              <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
                <FileText size={24} />
              </div>
              <div className="text-3xl font-black text-slate-900 mb-0.5">{stats?.total_interviews || 0}</div>
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Interviews</div>
            </div>
            
            <div className="bg-slate-50/50 rounded-2xl p-5 border border-slate-100 flex flex-col items-center justify-center text-center shadow-sm">
              <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3">
                <CheckCircle2 size={24} />
              </div>
              <div className="text-3xl font-black text-slate-900 mb-0.5">{stats?.completed_interviews || 0}</div>
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Completed</div>
            </div>
            
            <div className="bg-slate-50/50 rounded-2xl p-5 border border-slate-100 flex flex-col items-center justify-center text-center shadow-sm">
              <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3">
                <HelpCircle size={24} />
              </div>
              <div className="text-3xl font-black text-slate-900 mb-0.5">{stats?.total_questions || 0}</div>
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Questions</div>
            </div>
            
            <div className="bg-slate-50/50 rounded-2xl p-5 border border-slate-100 flex flex-col items-center justify-center text-center shadow-sm">
              <div className="w-12 h-12 rounded-full bg-purple-50 text-purple-600 flex items-center justify-center mb-3">
                <Edit3 size={24} />
              </div>
              <div className="text-3xl font-black text-slate-900 mb-0.5">{stats?.total_answered || 0}</div>
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest">Answered</div>
            </div>
          </div>
        </div>

        {/* Resume */}
        <div className="card p-6 shadow-sm flex flex-col border border-slate-100">
          <div className="flex items-center gap-2 mb-6 border-b border-slate-100/60 pb-4">
            <FileText size={18} className="text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Active Resume</h2>
          </div>
          
          {resume ? (
            <div className="flex-1 flex flex-col">
              <div className="flex items-center gap-4 p-5 bg-white rounded-xl border border-slate-200 mb-6 shadow-sm">
                <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-500 shrink-0">
                  <FileText size={20} />
                </div>
                <div className="min-w-0">
                  <div className="font-bold text-slate-900 truncate mb-1 text-sm">{resume.filename}</div>
                  <div className="badge badge-emerald py-0.5 text-[10px] uppercase tracking-wider">Active</div>
                </div>
              </div>
              
              {resume.skills && resume.skills.length > 0 && (
                <div className="flex-1">
                  <div className="eyebrow text-slate-500 mb-3">Extracted Skills ({resume.skills.length})</div>
                  <div className="flex flex-wrap gap-2 max-h-[220px] overflow-y-auto pr-2 custom-scrollbar">
                    {resume.skills.map(s => (
                      <span key={s} className="badge badge-indigo bg-white text-xs shadow-sm">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-slate-50 border-2 border-dashed border-slate-200 rounded-2xl">
              <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center mb-4 shadow-sm text-slate-300">
                <FileText size={32} />
              </div>
              <h3 className="text-base font-bold text-slate-900 mb-1">No Resume Found</h3>
              <p className="text-sm text-slate-500 font-medium max-w-[200px]">You haven't uploaded a resume to your profile yet.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
