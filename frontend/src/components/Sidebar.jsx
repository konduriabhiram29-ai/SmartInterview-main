import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, FileText, Clock, BarChart3,
  LogOut, BrainCircuit, Menu, X, User, BookOpen
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { to: '/dashboard', label: 'Dashboard',       icon: LayoutDashboard },
  { to: '/history',   label: 'Interviews',       icon: Clock },
  { to: '/resume',    label: 'Resume & Skills',  icon: FileText },
  { to: '/syllabus',  label: 'Syllabus & Course',icon: BookOpen },
  { to: '/performance', label: 'Analytics',      icon: BarChart3 },
  { to: '/profile',   label: 'Profile',          icon: User },
];

function SidebarContent({ onClose }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="flex flex-col h-full bg-white border-r border-slate-200 w-64">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-slate-100 flex-shrink-0">
        <Link
          to="/dashboard"
          onClick={onClose}
          className="flex items-center gap-2.5 font-bold text-lg tracking-tight no-underline text-slate-900"
        >
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <BrainCircuit size={17} className="text-white" />
          </div>
          Smart<span className="text-indigo-600">Interview</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-5 px-3 space-y-0.5">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-3">
          Main Menu
        </p>
        {navItems.map(({ to, label, icon: Icon }) => {
          const active = location.pathname.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              onClick={onClose}
              className={`nav-item no-underline ${active ? 'nav-item-active' : 'nav-item-inactive'}`}
            >
              <Icon size={16} className={active ? 'text-indigo-600' : 'text-slate-400'} />
              {label}
              {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-500" />}
            </Link>
          );
        })}

        {/* Status badge */}
        <div className="mt-6 mx-1">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-2 mb-2">
            Status
          </p>
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-emerald-50 border border-emerald-100">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-[pulse-dot_2s_ease-in-out_infinite]" />
            <span className="text-xs font-semibold text-emerald-700">AI Coach Online</span>
          </div>
        </div>
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-slate-100 flex-shrink-0">
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors">
          <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user?.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900 truncate">{user?.name}</p>
            <p className="text-xs text-slate-400 truncate">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            title="Logout"
            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors cursor-pointer bg-transparent border-none flex-shrink-0"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const { isAuthenticated } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (!isAuthenticated) return null;

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden flex items-center justify-between bg-white border-b border-slate-200 px-4 h-14 flex-shrink-0">
        <Link to="/dashboard" className="flex items-center gap-2 font-bold text-slate-900 no-underline">
          <div className="w-7 h-7 rounded-md bg-indigo-600 flex items-center justify-center">
            <BrainCircuit size={15} className="text-white" />
          </div>
          Smart<span className="text-indigo-600">Interview</span>
        </Link>
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 text-slate-500 hover:bg-slate-100 rounded-md cursor-pointer border-none bg-transparent"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="fixed inset-0 bg-slate-900/40" onClick={() => setMobileOpen(false)} />
          <div className="relative z-10 flex flex-col max-w-xs w-full shadow-xl">
            <div className="absolute top-3 right-[-48px]">
              <button
                onClick={() => setMobileOpen(false)}
                className="w-10 h-10 rounded-full bg-white/10 text-white flex items-center justify-center cursor-pointer border-none"
              >
                <X size={20} />
              </button>
            </div>
            <SidebarContent onClose={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden md:flex flex-col h-screen sticky top-0 flex-shrink-0">
        <SidebarContent onClose={() => {}} />
      </div>
    </>
  );
}
