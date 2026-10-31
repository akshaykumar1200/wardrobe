import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, Camera, Loader2, Image as ImageIcon } from 'lucide-react';
import { api } from '../api';

export default function Upload() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const navigate = useNavigate();

  const handleProcessFile = async (file) => {
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setError('Image must be under 10MB. Try a smaller photo.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const data = await api('/api/uploads', {
        method: 'POST',
        body: formData,
      });

      // Navigate to Review page with candidates
      navigate('/review', { state: { uploadData: data } });
    } catch (err) {
      setError(err.message || 'Segmentation failed. Please try a different photo.');
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleProcessFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <div className="text-center mb-10">
        <span className="text-xs font-medium uppercase tracking-widest text-ink-muted">
          AI Segmentation
        </span>
        <h1 className="font-display text-3xl sm:text-4xl text-ink font-normal mt-1">
          Add an Outfit Photo
        </h1>
        <p className="text-sm text-ink-muted mt-2 max-w-md mx-auto">
          Upload a full outfit photo. On-device SegFormer automatically isolates tops, bottoms, shoes, and accessories.
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-danger text-xs font-medium text-center max-w-lg mx-auto">
          {error}
        </div>
      )}

      {loading ? (
        <div className="bg-surface rounded-2xl border border-line p-12 text-center shadow-card max-w-lg mx-auto">
          <Loader2 className="w-10 h-10 text-sage animate-spin mx-auto mb-4" />
          <h3 className="font-display text-xl text-ink mb-1">Segmenting Garments...</h3>
          <p className="text-xs text-ink-muted">
            Running SegFormer AI pipeline locally to extract your items.
          </p>
        </div>
      ) : (
        <div className="max-w-lg mx-auto space-y-6">
          {/* Main Drag and Drop Box */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all ${
              isDragOver
                ? 'border-sage bg-sage-wash/50 scale-[1.01]'
                : 'border-line bg-surface hover:border-sage/50 hover:bg-paper/50'
            }`}
          >
            <div className="w-16 h-16 rounded-full bg-sage-wash text-sage flex items-center justify-center mx-auto mb-4">
              <UploadIcon className="w-7 h-7" />
            </div>

            <h3 className="font-display text-lg text-ink font-normal mb-1">
              Upload Outfit Image
            </h3>
            <p className="text-xs text-ink-muted mb-6">
              Drag & drop JPEG, PNG, or WebP up to 10MB
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  fileInputRef.current?.click();
                }}
                className="w-full sm:w-auto px-5 py-2.5 rounded-full bg-sage hover:bg-sage-deep text-paper font-medium text-xs uppercase tracking-wider transition-colors shadow-sm"
              >
                Choose File
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  cameraInputRef.current?.click();
                }}
                className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-line bg-surface text-ink hover:border-sage font-medium text-xs uppercase tracking-wider transition-colors"
              >
                <Camera className="w-4 h-4 inline mr-1.5" />
                Use Camera
              </button>
            </div>
          </div>

          {/* Hidden Inputs */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleProcessFile(e.target.files[0])}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleProcessFile(e.target.files[0])}
          />
        </div>
      )}
    </div>
  );
}
