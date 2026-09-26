import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { BrainCircuit, Eye, EyeOff, AlertCircle } from 'lucide-react';

export default function Register() {
  const [name, setName]                     = useState('');
  const [email, setEmail]                   = useState('');
  const [password, setPassword]             = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPw, setShowPw]                 = useState(false);
  const [error, setError]                   = useState('');
  const [loading, setLoading]               = useState(false);
  const { register } = useAuth();
  const navigate     = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) { setError('Passwords do not match'); return; }
    if (password.length < 6)          { setError('Password must be at least 6 characters'); return; }
    setLoading(true);
    try {
      await register(name, email, password, confirmPassword);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-indigo-600 flex-col justify-between p-12">
        <div className="flex items-center gap-2.5 text-white font-bold text-lg">
          <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center">
            <BrainCircuit size={18} className="text-white" />
          </div>
          SmartInterview
        </div>
        <div>
          <h2 className="text-3xl font-extrabold text-white leading-tight mb-4">
            Start your interview<br />preparation today.
          </h2>
          <p className="text-indigo-200 text-base leading-relaxed max-w-sm">
            Upload your resume, let the AI build your profile, and practice with questions tailored to your exact skills.
          </p>
        </div>
        <p className="text-indigo-300 text-xs">© 2026 SmartInterview Platform</p>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm">

          {/* Mobile logo */}
          <div className="flex items-center justify-center gap-2 text-slate-900 font-bold text-lg mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <BrainCircuit size={17} className="text-white" />
            </div>
            Smart<span className="text-indigo-600">Interview</span>
          </div>

          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight mb-1">Create your account</h1>
          <p className="text-sm text-slate-500 mb-8">Fill in the details below to get started.</p>

          {error && (
            <div className="error-banner mb-5">
              <AlertCircle size={15} className="flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label" htmlFor="name">Full Name</label>
              <input
                id="name" type="text" className="input"
                value={name} onChange={e => setName(e.target.value)}
                required placeholder="John Doe"
              />
            </div>
            <div>
              <label className="label" htmlFor="email">Email address</label>
              <input
                id="email" type="email" className="input"
                value={email} onChange={e => setEmail(e.target.value)}
                required autoComplete="email" placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <div className="relative">
                <input
                  id="password" type={showPw ? 'text' : 'password'} className="input pr-10"
                  value={password} onChange={e => setPassword(e.target.value)}
                  required placeholder="Min. 6 characters"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer bg-transparent border-none"
                  onClick={() => setShowPw(!showPw)}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div>
              <label className="label" htmlFor="confirmPassword">Confirm Password</label>
              <input
                id="confirmPassword" type="password" className="input"
                value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                required placeholder="••••••••"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary w-full py-2.5 text-sm mt-2"
              disabled={loading}
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-indigo-600 font-semibold no-underline hover:text-indigo-700">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
