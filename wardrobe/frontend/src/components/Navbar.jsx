import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Shirt, Upload, Shield, LogOut, Sparkles } from 'lucide-react';
import { api } from '../api';

export default function Navbar({ user, setUser }) {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout error:', err);
    }
    setUser(null);
    navigate('/login');
  };

  if (!user) return null;

  return (
    <header className="sticky top-0 z-50 bg-paper/80 backdrop-blur-md border-b border-line px-4 sm:px-8 py-3">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-ink font-display text-xl font-medium tracking-tight">
          <div className="w-8 h-8 rounded-lg bg-sage text-paper flex items-center justify-center font-bold text-sm shadow-sm">
            ✦
          </div>
          <span>Digital Wardrobe</span>
        </Link>

        <nav className="flex items-center gap-2 sm:gap-6">
          <Link
            to="/"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium uppercase tracking-widest transition-colors ${
              location.pathname === '/' ? 'bg-sage-wash text-sage-deep font-semibold' : 'text-ink-muted hover:text-ink'
            }`}
          >
            <Shirt className="w-4 h-4" />
            <span>Closet</span>
          </Link>

          <Link
            to="/upload"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium uppercase tracking-widest transition-colors ${
              location.pathname === '/upload' ? 'bg-sage-wash text-sage-deep font-semibold' : 'text-ink-muted hover:text-ink'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>Upload</span>
          </Link>

          {user.is_admin && (
            <Link
              to="/admin"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium uppercase tracking-widest transition-colors ${
                location.pathname === '/admin' ? 'bg-sage-wash text-sage-deep font-semibold' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <Shield className="w-4 h-4" />
              <span>Admin</span>
            </Link>
          )}

          <div className="h-4 w-px bg-line mx-1" />

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-block text-xs font-medium text-ink-muted">
              {user.display_name || user.email}
            </span>

            <Link to="/password" className="text-xs text-ink-muted hover:text-ink transition-colors">Change password</Link>

            <button
              onClick={handleLogout}
              className="p-1.5 rounded-full text-ink-muted hover:text-danger hover:bg-red-50 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </nav>
      </div>
    </header>
  );
}
