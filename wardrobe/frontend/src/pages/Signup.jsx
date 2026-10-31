import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Signup({ setUser }) {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password.length < 10) {
      setError('Password must be at least 10 characters long.');
      return;
    }

    setLoading(true);

    try {
      await api('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password, display_name: displayName })
      });

      // Auto login after signup
      const loginData = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });
      setUser(loginData.user);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface p-8 rounded-2xl border border-line shadow-card">
        <div className="text-center mb-8">
          <h1 className="font-display text-3xl font-normal text-ink mb-2">Create Account</h1>
          <p className="text-sm text-ink-muted">Join your personal digital wardrobe</p>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-danger text-xs font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">
              Display Name
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50"
              placeholder="e.g. Alex"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">
              Password (Min 10 chars)
            </label>
            <input
              type="password"
              required
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50"
              placeholder="••••••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-lg bg-sage hover:bg-sage-deep text-paper font-medium text-sm uppercase tracking-wider transition-colors shadow-sm disabled:opacity-50"
          >
            {loading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-ink-muted">
          Already have an account?{' '}
          <Link to="/login" className="text-sage font-medium hover:underline">
            Sign in here
          </Link>
        </div>
      </div>
    </div>
  );
}
