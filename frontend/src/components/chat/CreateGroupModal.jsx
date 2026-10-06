/**
 * CreateGroupModal — form to create a new chat group.
 * Searches users by name/email and adds them before creation.
 */
import { useState, useCallback } from 'react';
import { X, Search, Users, Plus, Trash2 } from 'lucide-react';
import { useChat } from '../../context/ChatContext';
import chatApi from '../../services/chatApi';

export default function CreateGroupModal({ onClose }) {
  const { createGroup } = useChat();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [searchQ, setSearchQ] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [searching, setSearching] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = useCallback(async (q) => {
    setSearchQ(q);
    if (q.length < 1) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const res = await chatApi.searchUsers(q);
      const users = res.data.users || [];
      const selectedIds = selectedUsers.map(u => u.id);
      setSearchResults(users.filter(u => !selectedIds.includes(u.id)));
    } catch { setSearchResults([]); }
    finally { setSearching(false); }
  }, [selectedUsers]);

  const addUser = (user) => {
    setSelectedUsers(prev => [...prev, user]);
    setSearchResults(prev => prev.filter(u => u.id !== user.id));
    setSearchQ('');
  };

  const removeUser = (userId) => {
    setSelectedUsers(prev => prev.filter(u => u.id !== userId));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) { setError('Group name is required.'); return; }
    setCreating(true);
    setError('');
    try {
      await createGroup({
        name: name.trim(),
        description: description.trim() || null,
        member_ids: selectedUsers.map(u => u.id),
      });
      onClose();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to create group.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center">
              <Users size={18} className="text-white" />
            </div>
            <h2 className="text-lg font-bold text-slate-900">New Group</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100
              rounded-lg transition-colors cursor-pointer border-none bg-transparent"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleCreate} className="p-5 space-y-4">
          {/* Group name */}
          <div>
            <label className="label">Group Name *</label>
            <input
              className="input"
              placeholder="e.g. DSA Study Group"
              value={name}
              onChange={e => setName(e.target.value)}
              maxLength={150}
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="label">Description</label>
            <textarea
              className="input resize-none"
              rows={2}
              placeholder="What is this group about?"
              value={description}
              onChange={e => setDescription(e.target.value)}
              maxLength={500}
            />
          </div>

          {/* Add members */}
          <div>
            <label className="label">Add Members</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                className="input pl-9"
                placeholder="Search by name or email..."
                value={searchQ}
                onChange={e => handleSearch(e.target.value)}
              />
            </div>

            {/* Search results */}
            {searchResults.length > 0 && (
              <div className="mt-1 border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                {searchResults.slice(0, 6).map(u => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => addUser(u)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-indigo-50
                      transition-colors cursor-pointer border-none bg-white text-left"
                  >
                    <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center
                      justify-center text-indigo-700 text-xs font-bold flex-shrink-0">
                      {u.name?.charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-900 truncate">{u.name}</div>
                      <div className="text-xs text-slate-500 truncate">{u.email}</div>
                    </div>
                    <Plus size={14} className="text-indigo-500 ml-auto flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}

            {/* Selected members */}
            {selectedUsers.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedUsers.map(u => (
                  <div
                    key={u.id}
                    className="flex items-center gap-1.5 bg-indigo-50 border border-indigo-100
                      rounded-full px-3 py-1 text-sm text-indigo-700"
                  >
                    <span className="font-medium truncate max-w-[120px]">{u.name}</span>
                    <button
                      type="button"
                      onClick={() => removeUser(u.id)}
                      className="text-indigo-400 hover:text-indigo-700 cursor-pointer
                        border-none bg-transparent p-0 flex-shrink-0"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary flex-1"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !name.trim()}
              className="btn btn-primary flex-1"
            >
              {creating ? 'Creating...' : 'Create Group'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
