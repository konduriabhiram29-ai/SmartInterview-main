/**
 * UnreadBadge — shows a red dot with count when unread > 0.
 */
export default function UnreadBadge({ count, className = '' }) {
  if (!count || count <= 0) return null;
  return (
    <span
      className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1
        rounded-full bg-red-500 text-white text-[10px] font-bold leading-none ${className}`}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}
