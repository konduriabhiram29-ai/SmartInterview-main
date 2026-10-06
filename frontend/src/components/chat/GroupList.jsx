/**
 * GroupList — Left panel: search bar, group items, create button.
 */
import { useState } from 'react';
import { Search, Plus, MessageSquare, Wifi, WifiOff } from 'lucide-react';
import { useChat } from '../../context/ChatContext';
import GroupListItem from './GroupListItem';
import CreateGroupModal from './CreateGroupModal';

export default function GroupList({ onSelectGroup }) {
  const { groups, groupsLoading, selectedGroupId, selectGroup, wsStatus, totalUnread } = useChat();
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);

  const filtered = groups.filter(g =>
    g.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelect = (groupId) => {
    selectGroup(groupId);
    onSelectGroup?.(groupId);
  };

  return (
    <div className="flex flex-col h-full bg-white border-r border-slate-100">
      {/* Header */}
      <div className="px-4 pt-4 pb-3 flex-shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900">Chats</h2>
            {totalUnread > 0 && (
              <span className="bg-indigo-600 text-white text-[10px] font-bold
                rounded-full px-1.5 py-0.5 min-w-[18px] text-center">
                {totalUnread > 99 ? '99+' : totalUnread}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* WS status indicator */}
            <span title={`WebSocket: ${wsStatus}`}>
              {wsStatus === 'connected'
                ? <Wifi size={14} className="text-emerald-500" />
                : <WifiOff size={14} className="text-slate-400" />}
            </span>
            <button
              onClick={() => setShowCreate(true)}
              className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg
                transition-colors cursor-pointer border-none bg-transparent"
              title="Create new group"
            >
              <Plus size={16} />
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="w-full pl-9 pr-3 py-2 text-sm bg-slate-50 border border-slate-100
              rounded-xl placeholder-slate-400 focus:outline-none focus:border-indigo-300
              focus:bg-white transition-all"
            placeholder="Search groups..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Group list */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
        {groupsLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-6 h-6 border-2 border-indigo-200 border-t-indigo-600
              rounded-full animate-spin" />
          </div>
        )}

        {!groupsLoading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center
              justify-center mb-3">
              <MessageSquare size={22} className="text-slate-400" />
            </div>
            {search ? (
              <p className="text-sm text-slate-500">No groups match &quot;{search}&quot;</p>
            ) : (
              <>
                <p className="text-sm font-semibold text-slate-700 mb-1">No groups yet</p>
                <p className="text-xs text-slate-400 mb-4">
                  Create a group to start chatting
                </p>
                <button
                  onClick={() => setShowCreate(true)}
                  className="btn btn-primary text-xs px-4 py-2"
                >
                  <Plus size={14} />
                  New Group
                </button>
              </>
            )}
          </div>
        )}

        {!groupsLoading && filtered.map(group => (
          <GroupListItem
            key={group.id}
            group={group}
            isSelected={selectedGroupId === group.id}
            onClick={() => handleSelect(group.id)}
          />
        ))}
      </div>

      {showCreate && <CreateGroupModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
