import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Login({ setUser }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });
      setUser(data.user);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface p-8 rounded-2xl border border-line shadow-card">
        <div className="text-center mb-8">
          <h1 className="font-display text-3xl font-normal text-ink mb-2">Welcome Back</h1>
          <p className="text-sm text-ink-muted">Sign in to access your digital wardrobe</p>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-danger text-xs font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
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
              Password
            </label>
            <input
              type="password"
              required
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
            {loading ? 'Signing In...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-ink-muted">
          Don't have an account?{' '}
          <Link to="/signup" className="text-sage font-medium hover:underline">
            Create one here
          </Link>
        </div>
        <p className="mt-3 text-center text-xs text-ink-muted">
          <Link to="/forgot" className="text-sage font-medium hover:underline">
            Forgot your password?
          </Link>{' '}An admin can also reset it for you.
        </p>
      </div>
    </div>
  );
}
