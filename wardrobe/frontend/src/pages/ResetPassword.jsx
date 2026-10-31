import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState(!token ? 'This reset link is invalid.' : '');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!token) {
      setError('This reset link is invalid.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await api('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password })
      });
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err.message || 'Password reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface p-8 rounded-2xl border border-line shadow-card">
        <div className="text-center mb-8">
          <h1 className="font-display text-3xl font-normal text-ink mb-2">Reset Password</h1>
          <p className="text-sm text-ink-muted">Choose a new password for your account</p>
        </div>

        {error && <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-danger text-xs font-medium">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">New Password</label>
            <input type="password" required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50"
              placeholder="••••••••••" />
          </div>
          <div>
            <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">Confirm Password</label>
            <input type="password" required minLength={10} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50"
              placeholder="••••••••••" />
          </div>
          <button type="submit" disabled={loading || !token}
            className="w-full py-3 px-4 rounded-lg bg-sage hover:bg-sage-deep text-paper font-medium text-sm uppercase tracking-wider transition-colors shadow-sm disabled:opacity-50">
            {loading ? 'Resetting...' : 'Reset Password'}
          </button>
        </form>
        <div className="mt-6 text-center text-xs text-ink-muted">
          <Link to="/login" className="text-sage font-medium hover:underline">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
