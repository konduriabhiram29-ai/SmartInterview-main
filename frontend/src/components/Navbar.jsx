import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { LayoutDashboard, FileText, Clock, User, LogOut, Menu, X, BrainCircuit, BarChart3, MessageSquare } from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/chat', label: 'Group Chat', icon: MessageSquare },
  { to: '/resume', label: 'Resume', icon: FileText },
  { to: '/history', label: 'History', icon: Clock },
  { to: '/performance', label: 'Performance', icon: BarChart3 },
];

export default function Navbar() {
  const { user, logout, isAuthenticated } = useAuth();
  const { totalUnread } = useChat();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  if (!isAuthenticated) return null;

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center gap-2 text-indigo-600 font-bold text-xl tracking-tight no-underline">
            <BrainCircuit size={28} className="text-indigo-600" />
            <span className="hidden sm:inline text-slate-900">Smart<span className="text-indigo-600">Interview</span></span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-2">
            {navItems.map(({ to, label, icon: Icon }) => {
              const isActive = location.pathname.startsWith(to);
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors no-underline ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <Icon size={18} className={isActive ? 'text-indigo-600' : 'text-slate-400'} />
                  {label}
                </Link>
              );
            })}
          </div>

          {/* User Menu & Chat Icon */}
          <div className="hidden md:flex items-center gap-4 border-l border-slate-200 pl-4">
            {/* Top-Right Chat Icon with Unread Badge */}
            <Link
              to="/chat"
              title="Group Chat"
              className="relative p-2 text-slate-600 hover:text-indigo-600 hover:bg-slate-100 rounded-xl transition-colors no-underline flex items-center justify-center cursor-pointer"
            >
              <MessageSquare size={20} />
              {totalUnread > 0 && (
                <span className="absolute -top-1 -right-1 bg-indigo-600 text-white text-[10px] font-bold rounded-full px-1.5 py-0.2 min-w-[18px] text-center shadow-xs">
                  {totalUnread > 99 ? '99+' : totalUnread}
                </span>
              )}
            </Link>

            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-sm">
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span className="text-sm font-medium text-slate-700">{user?.name}</span>
            </div>
            <button 
              onClick={handleLogout} 
              className="flex items-center gap-1.5 px-2 py-1.5 text-sm font-medium text-slate-500 hover:text-red-600 rounded-md hover:bg-red-50 transition-colors cursor-pointer bg-transparent border-none"
            >
              <LogOut size={18} />
              Logout
            </button>
          </div>

          {/* Mobile toggle */}
          <button 
            className="md:hidden p-2 rounded-md text-slate-400 hover:text-slate-500 hover:bg-slate-100 focus:outline-none cursor-pointer border-none bg-transparent" 
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white">
          <div className="px-2 pt-2 pb-3 space-y-1">
            {navItems.map(({ to, label, icon: Icon }) => {
              const isActive = location.pathname.startsWith(to);
              return (
                <Link
                  key={to}
                  to={to}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-3 px-3 py-3 rounded-md text-base font-medium no-underline ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <Icon size={20} className={isActive ? 'text-indigo-600' : 'text-slate-400'} />
                  {label}
                </Link>
              );
            })}
          </div>
          <div className="pt-4 pb-3 border-t border-slate-200 px-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-lg">
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div>
                <div className="text-base font-medium text-slate-800">{user?.name}</div>
                <div className="text-sm font-medium text-slate-500">{user?.email}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 px-3 py-2 text-base font-medium text-red-600 hover:bg-red-50 rounded-md cursor-pointer bg-transparent border-none"
            >
              <LogOut size={20} />
              Logout
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
