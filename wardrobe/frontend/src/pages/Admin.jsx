import React, { useState, useEffect } from 'react';
import { Users, HardDrive, Shirt, Upload, Calendar, ShieldCheck } from 'lucide-react';
import { api } from '../api';

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [resetResult, setResetResult] = useState(null);
  const [resetError, setResetError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const fetchAdminData = async () => {
      try {
        setLoading(true);
        const [statsData, usersData] = await Promise.all([
          api('/api/admin/stats'),
          api('/api/admin/users'),
        ]);
        setStats(statsData);
        setUsers(usersData);
      } catch (err) {
        setError(err.message || 'Access denied or error fetching admin metrics.');
      } finally {
        setLoading(false);
      }
    };
    fetchAdminData();
  }, []);

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const resetPassword = async (user) => {
    if (!window.confirm(`Reset the password for ${user.display_name || user.email}? This will sign them out of every device.`)) return;
    setResetError('');
    setResetResult(null);
    setCopied(false);
    try {
      const result = await api(`/api/admin/users/${user.id}/reset-password`, { method: 'POST' });
      setResetResult({ user, password: result.password });
    } catch (err) {
      setResetError(err.message || 'Could not reset password.');
    }
  };

  if (loading) {
    return <div className="py-24 text-center text-ink-muted text-sm">Loading admin metrics...</div>;
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto my-16 p-6 rounded-2xl bg-red-50 border border-red-200 text-danger text-center">
        <h3 className="font-display text-lg mb-2">Admin Access Error</h3>
        <p className="text-xs">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-sage font-semibold text-xs uppercase tracking-widest mb-1">
          <ShieldCheck className="w-4 h-4" />
          <span>System Administration</span>
        </div>
        <h1 className="font-display text-3xl sm:text-4xl text-ink font-normal">
          Dashboard & System Metrics
        </h1>
      </div>

      {/* Aggregate Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <div className="bg-surface p-5 rounded-2xl border border-line shadow-card">
            <div className="flex items-center justify-between text-ink-muted mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Total Users</span>
              <Users className="w-4 h-4 text-sage" />
            </div>
            <div className="font-display text-2xl text-ink">{stats.total_users}</div>
            <div className="text-[10px] text-ink-muted mt-1">{stats.active_users} active</div>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-card">
            <div className="flex items-center justify-between text-ink-muted mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Wardrobe Items</span>
              <Shirt className="w-4 h-4 text-sage" />
            </div>
            <div className="font-display text-2xl text-ink">{stats.total_items}</div>
            <div className="text-[10px] text-ink-muted mt-1">Across all users</div>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-card">
            <div className="flex items-center justify-between text-ink-muted mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Total Uploads</span>
              <Upload className="w-4 h-4 text-sage" />
            </div>
            <div className="font-display text-2xl text-ink">{stats.total_uploads}</div>
            <div className="text-[10px] text-ink-muted mt-1">{stats.signups_last_7d} signups (7d)</div>
          </div>

          <div className="bg-surface p-5 rounded-2xl border border-line shadow-card">
            <div className="flex items-center justify-between text-ink-muted mb-2">
              <span className="text-xs font-medium uppercase tracking-wider">Storage Used</span>
              <HardDrive className="w-4 h-4 text-sage" />
            </div>
            <div className="font-display text-2xl text-ink">{formatBytes(stats.storage_bytes)}</div>
            <div className="text-[10px] text-ink-muted mt-1">Originals + Cutouts</div>
          </div>
        </div>
      )}

      {/* User Directory Table */}
      {(resetResult || resetError) && (
        <div className="mb-4 p-4 rounded-xl bg-surface border border-line text-xs text-ink">
          {resetResult && <>
            <p className="mb-2">Give this password to {resetResult.user.display_name || resetResult.user.email} now. It will not be shown again.</p>
            <div className="flex items-center gap-2">
              <code className="px-3 py-2 rounded-lg bg-paper border border-line select-all">{resetResult.password}</code>
              <button onClick={async () => { await navigator.clipboard.writeText(resetResult.password); setCopied(true); }} className="px-3 py-2 rounded-lg border border-line text-ink-muted hover:text-ink transition-colors">{copied ? 'Copied' : 'Copy'}</button>
              <button onClick={() => setResetResult(null)} className="px-3 py-2 rounded-lg border border-line text-ink-muted hover:text-ink transition-colors">Close</button>
            </div>
          </>}
          {resetError && <p className="text-danger">{resetError}</p>}
        </div>
      )}
      <div className="bg-surface rounded-2xl border border-line shadow-card overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="font-display text-lg text-ink font-normal">User Directory</h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-paper/50 text-[10px] font-medium uppercase tracking-widest text-ink-muted border-b border-line">
                <th className="px-6 py-3">User</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Items</th>
                <th className="px-6 py-3">Uploads</th>
                <th className="px-6 py-3">Joined</th>
                <th className="px-6 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line text-xs">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-paper/30 transition-colors">
                  <td className="px-6 py-3.5">
                    <div className="font-medium text-ink">{u.display_name || 'User'}</div>
                    <div className="text-ink-muted text-[11px]">{u.email}</div>
                  </td>
                  <td className="px-6 py-3.5">
                    {u.is_admin ? (
                      <span className="px-2 py-0.5 rounded-full bg-sage-wash text-sage-deep font-semibold text-[10px]">
                        Admin
                      </span>
                    ) : (
                      <span className="text-ink-muted">User</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 text-ink font-medium">{u.item_count}</td>
                  <td className="px-6 py-3.5 text-ink-muted">{u.upload_count}</td>
                  <td className="px-6 py-3.5 text-ink-muted">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}
                  </td>
                  <td className="px-6 py-3.5">
                    <button onClick={() => resetPassword(u)} className="px-3 py-1.5 rounded-lg border border-line text-ink-muted hover:text-ink transition-colors">Reset password</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
