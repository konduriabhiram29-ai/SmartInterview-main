/**
 * MessageInput — Input bar at the bottom of the chat view.
 * Features:
 *  - Auto-resizing textarea / input
 *  - Enter to send, Shift+Enter for new line
 *  - Typing debounce events to WebSocket
 *  - Share interview shortcut for Admins
 *  - Responsive layout
 */

import { useState, useRef, useEffect } from 'react';
import { Send, Share2 } from 'lucide-react';
import { useChat } from '../../context/ChatContext';

export default function MessageInput({
  groupId,
  isAdmin = false,
  onOpenShareInterview,
  disabled = false,
}) {
  const [text, setText] = useState('');
  const { sendMessage, handleTyping } = useChat();
  const inputRef = useRef(null);

  // Focus input when group changes
  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [groupId, disabled]);

  const handleChange = (e) => {
    setText(e.target.value);
    if (groupId) {
      handleTyping(groupId);
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || !groupId || disabled) return;
    sendMessage(groupId, trimmed);
    setText('');
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="bg-white border-t border-slate-200 px-4 py-3">
      <div className="flex items-end gap-2 max-w-5xl mx-auto">
        {/* Share Interview Button (visible/active for admin) */}
        {isAdmin && onOpenShareInterview && (
          <button
            type="button"
            onClick={onOpenShareInterview}
            title="Share an Interview with this group"
            className="p-2.5 text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-xl transition-colors cursor-pointer border border-indigo-200/60 flex items-center justify-center flex-shrink-0"
          >
            <Share2 size={18} />
          </button>
        )}

        {/* Text Input area */}
        <div className="flex-1 relative bg-slate-50 border border-slate-200 focus-within:border-indigo-500 focus-within:bg-white rounded-2xl transition-all shadow-inner">
          <textarea
            ref={inputRef}
            rows={1}
            value={text}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={
              disabled
                ? 'Connecting to chat...'
                : 'Type a message... (Enter to send, Shift+Enter for new line)'
            }
            className="w-full px-4 py-2.5 bg-transparent border-none text-slate-800 placeholder-slate-400 text-sm resize-none focus:outline-none max-h-32 min-h-[40px]"
            style={{ height: 'auto' }}
          />
        </div>

        {/* Send Button */}
        <button
          type="button"
          onClick={handleSend}
          disabled={!text.trim() || disabled}
          className={`p-2.5 rounded-xl flex items-center justify-center flex-shrink-0 transition-all ${
            text.trim() && !disabled
              ? 'bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer shadow-sm shadow-indigo-200'
              : 'bg-slate-100 text-slate-300 cursor-not-allowed border border-slate-200/50'
          }`}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
