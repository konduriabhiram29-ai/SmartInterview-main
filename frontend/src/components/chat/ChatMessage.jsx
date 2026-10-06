/**
 * ChatMessage — Renders an individual message inside the chat thread.
 * Handles:
 *  - TEXT messages (own vs others)
 *  - INTERVIEW cards
 *  - INTERVIEW_RESULT cards
 *  - SYSTEM notices
 *  - Delivery status icons (pending, sent, delivered, read)
 */

import { Check, CheckCheck, Clock } from 'lucide-react';
import InterviewMessageCard from './InterviewMessageCard';
import InterviewResultCard from './InterviewResultCard';

function formatMessageTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Consistent sender color palette
const SENDER_COLORS = [
  'text-indigo-600',
  'text-purple-600',
  'text-pink-600',
  'text-rose-600',
  'text-orange-600',
  'text-amber-600',
  'text-emerald-600',
  'text-teal-600',
  'text-cyan-600',
  'text-blue-600',
];

function getSenderColor(name = '') {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return SENDER_COLORS[Math.abs(hash) % SENDER_COLORS.length];
}

export default function ChatMessage({ message, isOwn, showSender = true }) {
  const {
    message_type = 'TEXT',
    content,
    sender_name,
    created_at,
    status = 'sent',
  } = message;

  // 1. System messages
  if (message_type === 'SYSTEM') {
    return (
      <div className="flex justify-center my-3">
        <span className="bg-slate-100 text-slate-500 text-xs px-3.5 py-1 rounded-full font-medium tracking-wide shadow-xs border border-slate-200/50">
          {content}
        </span>
      </div>
    );
  }

  // 2. Interview Share Card
  if (message_type === 'INTERVIEW') {
    return (
      <div className="flex justify-center my-4 w-full">
        <InterviewMessageCard message={message} />
      </div>
    );
  }

  // 3. Interview Result Card
  if (message_type === 'INTERVIEW_RESULT') {
    return (
      <div className="flex justify-center my-4 w-full">
        <InterviewResultCard message={message} />
      </div>
    );
  }

  // 4. Standard Text Message Bubble
  return (
    <div className={`flex flex-col mb-2.5 ${isOwn ? 'items-end' : 'items-start'}`}>
      <div
        className={`max-w-[75%] sm:max-w-[65%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed shadow-xs transition-all ${
          isOwn
            ? 'bg-indigo-600 text-white rounded-tr-xs'
            : 'bg-white text-slate-800 border border-slate-150 rounded-tl-xs shadow-slate-100'
        }`}
      >
        {/* Sender Name for group chats when incoming */}
        {!isOwn && showSender && sender_name && (
          <p className={`text-xs font-semibold mb-1 ${getSenderColor(sender_name)}`}>
            {sender_name}
          </p>
        )}

        {/* Message content */}
        <p className="whitespace-pre-wrap break-words">{content}</p>

        {/* Time and Status metadata */}
        <div
          className={`flex items-center justify-end gap-1 mt-1 text-[10px] select-none ${
            isOwn ? 'text-indigo-200' : 'text-slate-400'
          }`}
        >
          <span>{formatMessageTime(created_at)}</span>
          {isOwn && (
            <span className="flex items-center">
              {status === 'pending' && <Clock size={11} className="animate-pulse" />}
              {status === 'sent' && <Check size={12} />}
              {status === 'delivered' && <CheckCheck size={12} />}
              {status === 'read' && <CheckCheck size={12} className="text-sky-300" />}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
