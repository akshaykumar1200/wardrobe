import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await api('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email })
      });
      setSubmitted(true);
    } catch (err) {
      setError(err.message || 'Request failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface p-8 rounded-2xl border border-line shadow-card">
        <div className="text-center mb-8">
          <h1 className="font-display text-3xl font-normal text-ink mb-2">Forgot Password</h1>
          <p className="text-sm text-ink-muted">Enter your email to reset your password</p>
        </div>

        {error && <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-danger text-xs font-medium">{error}</div>}
        {submitted ? (
          <p className="text-sm text-ink-muted text-center">If that address has an account, a reset link is on its way.</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">Email Address</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50"
                placeholder="you@example.com" />
            </div>
            <button type="submit" disabled={loading}
              className="w-full py-3 px-4 rounded-lg bg-sage hover:bg-sage-deep text-paper font-medium text-sm uppercase tracking-wider transition-colors shadow-sm disabled:opacity-50">
              {loading ? 'Sending...' : 'Send Reset Link'}
            </button>
          </form>
        )}
        <div className="mt-6 text-center text-xs text-ink-muted">
          <Link to="/login" className="text-sage font-medium hover:underline">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
