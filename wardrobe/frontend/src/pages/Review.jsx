import React, { useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { Check, Trash2, ArrowLeft, Plus } from 'lucide-react';
import { api } from '../api';

export default function Review() {
  const location = useLocation();
  const navigate = useNavigate();
  const uploadData = location.state?.uploadData;

  const [candidates, setCandidates] = useState(
    uploadData?.candidates || []
  );
  const [saving, setSaving] = useState(false);

  if (!uploadData) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center">
        <h2 className="font-display text-2xl text-ink mb-3">No Upload Data</h2>
        <p className="text-sm text-ink-muted mb-6">Please upload an outfit photo first.</p>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-sage text-paper text-xs font-medium uppercase tracking-wider"
        >
          Go to Upload
        </Link>
      </div>
    );
  }

  const handleUpdateCandidate = (index, field, value) => {
    const next = [...candidates];
    next[index] = { ...next[index], [field]: value };
    setCandidates(next);
  };

  const handleRemoveCandidate = (index) => {
    setCandidates(candidates.filter((_, i) => i !== index));
  };

  const handleConfirmAll = async () => {
    if (candidates.length === 0) {
      navigate('/');
      return;
    }

    setSaving(true);
    try {
      for (const item of candidates) {
        await api('/api/items', {
          method: 'POST',
          body: JSON.stringify({
            name: item.name,
            category: item.category,
            stored_name: item.stored_name,
            color: item.color,
            bytes: item.bytes,
            upload_id: uploadData.upload_id,
            is_manual: 0,
          }),
        });
      }
      navigate('/');
    } catch (err) {
      alert('Failed to save items: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <button
        onClick={() => navigate('/upload')}
        className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-widest text-ink-muted hover:text-ink mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Upload</span>
      </button>

      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div>
          <span className="text-xs font-medium uppercase tracking-widest text-ink-muted">
            Candidate Review
          </span>
          <h1 className="font-display text-3xl text-ink font-normal mt-1">
            Detected Pieces ({candidates.length})
          </h1>
        </div>

        <button
          onClick={handleConfirmAll}
          disabled={saving || candidates.length === 0}
          className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full bg-sage hover:bg-sage-deep text-paper font-medium text-xs uppercase tracking-wider transition-colors shadow-sm disabled:opacity-50"
        >
          <Check className="w-4 h-4" />
          <span>{saving ? 'Saving...' : 'Confirm & Save to Closet'}</span>
        </button>
      </div>

      {candidates.length === 0 ? (
        <div className="bg-surface rounded-2xl border border-line p-12 text-center">
          <p className="text-sm text-ink-muted mb-4">No candidate items remaining.</p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-line text-xs font-medium uppercase tracking-wider text-ink"
          >
            Upload Another Photo
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {candidates.map((c, idx) => (
            <div
              key={idx}
              className="bg-surface rounded-2xl border border-line p-5 flex gap-5 items-center shadow-card relative"
            >
              <div className="w-28 h-28 flex items-center justify-center p-2 rounded-xl bg-paper border border-line flex-shrink-0">
                <img
                  src={c.image_url}
                  alt={c.name}
                  className="max-w-full max-h-full object-contain garment-flatlay"
                />
              </div>

              <div className="flex-1 space-y-3">
                <div>
                  <label className="block text-[10px] font-medium uppercase tracking-widest text-ink-muted mb-1">
                    Piece Name
                  </label>
                  <input
                    type="text"
                    value={c.name}
                    onChange={(e) => handleUpdateCandidate(idx, 'name', e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-line text-sm text-ink focus:outline-none focus:border-sage bg-paper/50"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <label className="block text-[10px] font-medium uppercase tracking-widest text-ink-muted mb-1">
                      Category
                    </label>
                    <select
                      value={c.category}
                      onChange={(e) => handleUpdateCandidate(idx, 'category', e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg border border-line text-xs text-ink focus:outline-none focus:border-sage bg-surface"
                    >
                      <option value="topwear">Topwear</option>
                      <option value="bottomwear">Bottomwear</option>
                      <option value="shoes">Shoes</option>
                      <option value="accessories">Accessories</option>
                      <option value="other">Other</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-widest text-ink-muted mb-1">
                      Color
                    </label>
                    <input
                      type="color"
                      value={c.color || '#7d8c71'}
                      onChange={(e) => handleUpdateCandidate(idx, 'color', e.target.value)}
                      className="w-8 h-8 rounded-lg border border-line p-0.5 cursor-pointer"
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleRemoveCandidate(idx)}
                className="absolute top-3 right-3 p-1 text-ink-muted hover:text-danger rounded-full hover:bg-red-50 transition-colors"
                title="Discard Piece"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
