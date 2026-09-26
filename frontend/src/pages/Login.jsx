import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { BrainCircuit, Eye, EyeOff, AlertCircle } from 'lucide-react';

export default function Login() {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const { login }    = useAuth();
  const navigate     = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid email or password');
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
            Your AI interview<br />coach is ready.
          </h2>
          <p className="text-indigo-200 text-base leading-relaxed max-w-sm">
            Adaptive questions, real-time scoring, and detailed feedback — all personalised to your resume.
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

          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight mb-1">Welcome back</h1>
          <p className="text-sm text-slate-500 mb-8">Enter your credentials to continue.</p>

          {error && (
            <div className="error-banner mb-5">
              <AlertCircle size={15} className="flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
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
                  required autoComplete="current-password" placeholder="••••••••"
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
            <button
              type="submit"
              className="btn btn-primary w-full py-2.5 text-sm mt-2"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-indigo-600 font-semibold no-underline hover:text-indigo-700">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
