/**
 * GroupListItem — Single row in the left-panel group list.
 */
import UnreadBadge from './UnreadBadge';

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function getMessagePreview(msg) {
  if (!msg) return 'No messages yet';
  if (msg.message_type === 'SYSTEM') return msg.content?.text || '';
  if (msg.message_type === 'INTERVIEW') return '📋 Interview shared';
  if (msg.message_type === 'INTERVIEW_RESULT') return '🏆 Result published';
  return msg.content?.text || '';
}

function GroupAvatar({ name, size = 'md' }) {
  const initials = name
    ?.split(' ')
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase() || '?';
  const sz = size === 'sm' ? 'w-8 h-8 text-xs' : 'w-11 h-11 text-sm';
  const colors = [
    'bg-indigo-500', 'bg-violet-500', 'bg-emerald-500',
    'bg-amber-500', 'bg-rose-500', 'bg-sky-500', 'bg-pink-500',
  ];
  const color = colors[(name?.charCodeAt(0) || 0) % colors.length];
  return (
    <div className={`${sz} ${color} rounded-full flex items-center justify-center
      text-white font-bold flex-shrink-0`}>
      {initials}
    </div>
  );
}

export { GroupAvatar };

export default function GroupListItem({ group, isSelected, onClick }) {
  const lastMsg = group.last_message;
  const preview = getMessagePreview(lastMsg);
  const time = formatTime(lastMsg?.created_at || group.created_at);

  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-center gap-3 px-3 py-3 rounded-xl
        transition-all duration-150 hover:bg-slate-50 cursor-pointer border-none
        ${isSelected ? 'bg-indigo-50 border border-indigo-100' : 'bg-transparent'}`}
    >
      <GroupAvatar name={group.name} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className={`text-sm font-semibold truncate
            ${isSelected ? 'text-indigo-700' : 'text-slate-900'}`}>
            {group.name}
          </span>
          <span className="text-[10px] text-slate-400 flex-shrink-0">{time}</span>
        </div>
        <div className="flex items-center justify-between gap-2 mt-0.5">
          <span className="text-xs text-slate-500 truncate">{preview}</span>
          {group.unread_count > 0 && (
            <UnreadBadge count={group.unread_count} />
          )}
        </div>
      </div>
    </button>
  );
}
