import React, { useState } from 'react';
import { api } from '../api';

export default function ChangePassword() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await api('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setSuccess('Password changed successfully.');
    } catch (err) {
      setError(err.message || 'Could not change password.');
    } finally {
      setLoading(false);
    }
  };

  const inputClass = 'w-full px-4 py-2.5 rounded-lg border border-line focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage text-sm bg-paper/50';
  const labelClass = 'block text-xs font-medium uppercase tracking-widest text-ink-muted mb-2';

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface p-8 rounded-2xl border border-line shadow-card">
        <div className="text-center mb-8">
          <h1 className="font-display text-3xl font-normal text-ink mb-2">Change Password</h1>
          <p className="text-sm text-ink-muted">Choose a new password for your account</p>
        </div>

        {error && <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 text-danger text-xs font-medium">{error}</div>}
        {success && <div className="mb-6 p-3 rounded-lg bg-sage-wash border border-line text-sage-deep text-xs font-medium">{success}</div>}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className={labelClass}>Current Password</label>
            <input type="password" required value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>New Password</label>
            <input type="password" required minLength={10} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Confirm New Password</label>
            <input type="password" required minLength={10} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className={inputClass} />
          </div>
          <button type="submit" disabled={loading} className="w-full py-3 px-4 rounded-lg bg-sage hover:bg-sage-deep text-paper font-medium text-sm uppercase tracking-wider transition-colors shadow-sm disabled:opacity-50">
            {loading ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>
    </div>
  );
}
