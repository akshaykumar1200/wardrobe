import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Search, Plus, Trash2, Edit2, Sparkles, Filter, X } from 'lucide-react';
import { api } from '../api';

const CATEGORIES = [
  { key: 'all', label: 'All Pieces' },
  { key: 'topwear', label: 'Topwear' },
  { key: 'bottomwear', label: 'Bottomwear' },
  { key: 'shoes', label: 'Shoes' },
  { key: 'accessories', label: 'Accessories' },
  { key: 'other', label: 'Other' },
];

export default function Closet() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCat, setSelectedCat] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [flatItem, setFlatItem] = useState(null);
  const [flatResult, setFlatResult] = useState(null);
  const [flatLoading, setFlatLoading] = useState(false);
  const [flatError, setFlatError] = useState('');
  const flatRequestInProgress = useRef(false);

  const makeFlatView = async (item) => {
    if (flatRequestInProgress.current) return;
    flatRequestInProgress.current = true;
    setFlatItem(item);
    setFlatResult(null);
    setFlatError('');
    setFlatLoading(true);
    try {
      const result = await api(`/api/items/${item.id}/flat`, { method: 'POST' });
      setFlatResult({ ...result, cacheVersion: Date.now() });
    } catch (err) {
      setFlatError(err.message || 'Could not make a flat view.');
    } finally {
      flatRequestInProgress.current = false;
      setFlatLoading(false);
    }
  };

  const fetchItems = async () => {
    try {
      setLoading(true);
      let path = '/api/items';
      const params = new URLSearchParams();
      if (selectedCat !== 'all') params.append('category', selectedCat);
      if (searchQuery) params.append('q', searchQuery);
      if (params.toString()) path += `?${params.toString()}`;

      const data = await api(path);
      setItems(data);
    } catch (err) {
      console.error('Failed to fetch items:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [selectedCat, searchQuery]);

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this piece from your wardrobe?')) return;
    try {
      await api(`/api/items/${id}`, { method: 'DELETE' });
      setItems(items.filter((i) => i.id !== id));
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editingItem) return;

    try {
      const updated = await api(`/api/items/${editingItem.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: editingItem.name,
          category: editingItem.category,
          color: editingItem.color,
        }),
      });
      setItems(items.map((i) => (i.id === updated.id ? updated : i)));
      setEditingItem(null);
    } catch (err) {
      alert('Update failed: ' + err.message);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-8 py-8">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <span className="text-xs font-medium uppercase tracking-widest text-ink-muted">
            Personal Collection
          </span>
          <h1 className="font-display text-3xl sm:text-4xl text-ink font-normal mt-1">
            Your Digital Closet
          </h1>
        </div>

        <Link
          to="/upload"
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full bg-sage hover:bg-sage-deep text-paper font-medium text-xs uppercase tracking-wider transition-colors shadow-sm self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Add New Piece</span>
        </Link>
      </div>

      {/* Controls & Category Filter Chips */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 mb-8">
        {/* Category Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0 scrollbar-none">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setSelectedCat(cat.key)}
              className={`px-4 py-1.5 rounded-full text-xs font-medium uppercase tracking-wider transition-all whitespace-nowrap ${
                selectedCat === cat.key
                  ? 'bg-sage text-paper shadow-sm'
                  : 'bg-surface text-ink-muted border border-line hover:text-ink hover:border-sage'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Search Bar */}
        <div className="relative w-full sm:w-64">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search closet..."
            className="w-full pl-9 pr-4 py-1.5 rounded-full border border-line bg-surface text-sm focus:outline-none focus:border-sage text-ink placeholder:text-ink-muted/60"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Main Wardrobe Flat-Lay Grid */}
      {loading ? (
        <div className="py-24 text-center text-ink-muted text-sm font-medium">
          Loading collection...
        </div>
      ) : items.length === 0 ? (
        <div className="py-24 text-center border border-dashed border-line rounded-2xl bg-surface/50 max-w-md mx-auto p-8">
          <div className="w-12 h-12 rounded-full bg-sage-wash text-sage flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-6 h-6" />
          </div>
          <h3 className="font-display text-xl text-ink font-normal mb-2">
            Your closet is empty
          </h3>
          <p className="text-sm text-ink-muted mb-6">
            Upload your first outfit photo to isolate and save your pieces.
          </p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-sage hover:bg-sage-deep text-paper font-medium text-xs uppercase tracking-wider transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add your first piece</span>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-5 sm:gap-6">
          {items.map((item) => (
            <div key={item.id} className="group relative flex flex-col">
              {/* Garment Flat-Lay Cutout Stage */}
              <div className="garment-card">
                <img
                  src={item.image_url}
                  alt={item.name}
                  loading="lazy"
                  className="garment-flatlay"
                />

                {/* Hover Actions */}
                <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity flex gap-1 bg-surface/90 backdrop-blur-sm p-1 rounded-full border border-line shadow-sm">
                  {item.category === 'topwear' && (
                    <button
                      onClick={() => makeFlatView(item)}
                      disabled={flatLoading}
                      className="px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-ink-muted hover:text-ink disabled:opacity-50"
                      title="Flat view"
                    >
                      Flat view
                    </button>
                  )}
                  <button
                    onClick={() => setEditingItem(item)}
                    className="p-1 text-ink-muted hover:text-ink"
                    title="Edit"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(item.id)}
                    className="p-1 text-ink-muted hover:text-danger"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Garment Label & Category */}
              <div className="pt-3 px-0.5">
                <div className="font-display text-sm text-ink font-normal truncate">
                  {item.name}
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  {item.color && (
                    <span
                      className="w-2.5 h-2.5 rounded-full border border-line shrink-0"
                      style={{ backgroundColor: item.color }}
                    />
                  )}
                  <span className="text-[10px] font-medium uppercase tracking-widest text-ink-muted truncate">
                    {item.category}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface rounded-2xl border border-line max-w-md w-full p-6 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-xl text-ink">Edit Piece</h3>
              <button
                onClick={() => setEditingItem(null)}
                className="text-ink-muted hover:text-ink"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdate} className="space-y-4">
              <div className="garment-card !aspect-[3/2] !bg-paper">
                <img
                  src={editingItem.image_url}
                  alt={editingItem.name}
                  className="garment-flatlay"
                />
              </div>

              <div>
                <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-1">
                  Name
                </label>
                <input
                  type="text"
                  required
                  value={editingItem.name}
                  onChange={(e) =>
                    setEditingItem({ ...editingItem, name: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-lg border border-line text-sm text-ink focus:outline-none focus:border-sage"
                />
              </div>

              <div>
                <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-1">
                  Category
                </label>
                <select
                  value={editingItem.category}
                  onChange={(e) =>
                    setEditingItem({ ...editingItem, category: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-lg border border-line text-sm text-ink focus:outline-none focus:border-sage bg-surface"
                >
                  <option value="topwear">Topwear</option>
                  <option value="bottomwear">Bottomwear</option>
                  <option value="shoes">Shoes</option>
                  <option value="accessories">Accessories</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium uppercase tracking-widest text-ink-muted mb-1">
                  Color Accent
                </label>
                <input
                  type="color"
                  value={editingItem.color || '#7d8c71'}
                  onChange={(e) =>
                    setEditingItem({ ...editingItem, color: e.target.value })
                  }
                  className="w-full h-9 rounded-lg border border-line p-1 cursor-pointer"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="px-4 py-2 rounded-lg border border-line text-xs font-medium uppercase tracking-wider text-ink-muted hover:bg-paper"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-sage hover:bg-sage-deep text-paper text-xs font-medium uppercase tracking-wider transition-colors"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Flat View Modal */}
      {flatItem && (
        <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface rounded-2xl border border-line max-w-2xl w-full p-6 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-xl text-ink">Flat View</h3>
              <button
                onClick={() => setFlatItem(null)}
                className="text-ink-muted hover:text-ink"
                aria-label="Close flat view"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {flatLoading ? (
              <p className="py-10 text-center text-sm text-ink-muted">
                Making a flat view from your photo... this takes about a minute
              </p>
            ) : flatError ? (
              <div className="rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
                {flatError}
              </div>
            ) : flatResult ? (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">Original cut-out</div>
                    <div className="garment-card !aspect-[3/2] !bg-paper">
                      <img src={flatItem.image_url} alt={`${flatItem.name} original cut-out`} className="garment-flatlay" />
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium uppercase tracking-widest text-ink-muted mb-2">Flat view</div>
                    <div className="garment-card !aspect-[3/2] !bg-paper">
                      <img src={`/api/images/item/${flatResult.stored_name}?v=${flatResult.cacheVersion}`} alt={`${flatItem.name} flat view`} className="garment-flatlay" />
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-ink-muted">
                  AI-adjusted: your photo's real pixels rearranged into a flat shape. Areas hidden in the photo were filled in.
                  {flatResult.hem_extended && ' The bottom edge was cut off in your photo and has been filled in.'}
                </p>
                <div className="flex justify-end pt-4">
                  <button
                    onClick={() => makeFlatView(flatItem)}
                    disabled={flatLoading}
                    className="px-4 py-2 rounded-lg bg-sage hover:bg-sage-deep text-paper text-xs font-medium uppercase tracking-wider transition-colors disabled:opacity-50"
                  >
                    Regenerate
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
