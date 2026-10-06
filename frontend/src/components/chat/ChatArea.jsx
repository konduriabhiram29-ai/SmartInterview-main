/**
 * ChatArea — Main chat conversation view with WhatsApp-inspired aesthetics.
 * Handles:
 *  - Header with group info, typing status, and action buttons
 *  - Date-grouped message thread with auto-scroll and pagination (infinite scroll up)
 *  - Typing indicators with micro-animations
 *  - Responsive mobile back button
 *  - Modals for Share Interview and Group Details / Admin Dashboard
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  ArrowLeft, MoreVertical, Share2, Info, MessageSquare,
  ChevronDown, WifiOff, Users
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useChat } from '../../context/ChatContext';
import ChatMessage from './ChatMessage';
import MessageInput from './MessageInput';
import ShareInterviewModal from './ShareInterviewModal';
import GroupDetailsModal from './GroupDetailsModal';
import { GroupAvatar } from './GroupListItem';

function formatDividerDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return 'Today';
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

export default function ChatArea({ onBack }) {
  const { user } = useAuth();
  const {
    groups,
    selectedGroupId,
    messages,
    messagesLoading,
    loadMessages,
    hasMore,
    nextCursor,
    typingUsers,
    wsStatus,
  } = useChat();

  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [detailsModalOpen, setDetailsModalOpen] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);

  const messagesEndRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const previousScrollHeight = useRef(0);

  // Active group data
  const currentGroup = useMemo(
    () => groups.find((g) => g.id === selectedGroupId),
    [groups, selectedGroupId]
  );

  const currentMessages = useMemo(
    () => (selectedGroupId ? messages[selectedGroupId] || [] : []),
    [messages, selectedGroupId]
  );

  // Check if current user is admin of this group
  const isAdmin = useMemo(() => {
    if (!currentGroup || !user) return false;
    if (currentGroup.created_by === user.id) return true;
    const member = currentGroup.members?.find((m) => m.user_id === user.id);
    return member?.role === 'ADMIN';
  }, [currentGroup, user]);

  // Typing status for this group
  const groupTyping = typingUsers[selectedGroupId] || {};
  const typingNames = Object.values(groupTyping);
  const typingText = useMemo(() => {
    if (typingNames.length === 0) return null;
    if (typingNames.length === 1) return `${typingNames[0]} is typing...`;
    if (typingNames.length === 2) return `${typingNames[0]} and ${typingNames[1]} are typing...`;
    return 'Several people are typing...';
  }, [typingNames]);

  // Auto-scroll to bottom on initial message load or when own message sent
  useEffect(() => {
    if (currentMessages.length > 0 && !loadingOlder) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [selectedGroupId, currentMessages.length, loadingOlder]);

  // Handle scroll for pagination & scroll-to-bottom button
  const handleScroll = useCallback(async () => {
    const el = scrollContainerRef.current;
    if (!el) return;

    // Show/hide scroll to bottom button
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBottom(distanceFromBottom > 200);

    // Load older messages if scrolled to top
    if (el.scrollTop < 60 && hasMore[selectedGroupId] && !messagesLoading && !loadingOlder) {
      setLoadingOlder(true);
      previousScrollHeight.current = el.scrollHeight;
      const cursor = nextCursor[selectedGroupId];
      await loadMessages(selectedGroupId, cursor);
      setLoadingOlder(false);

      // Preserve scroll position
      requestAnimationFrame(() => {
        if (el) {
          el.scrollTop = el.scrollHeight - previousScrollHeight.current;
        }
      });
    }
  }, [selectedGroupId, hasMore, messagesLoading, loadingOlder, nextCursor, loadMessages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Group messages by date
  const groupedMessages = useMemo(() => {
    const groupsList = [];
    let lastDateStr = null;

    currentMessages.forEach((msg) => {
      const dateStr = formatDividerDate(msg.created_at);
      if (dateStr !== lastDateStr) {
        groupsList.push({ type: 'date', date: dateStr, key: `date-${dateStr}-${msg.id || msg.client_message_id}` });
        lastDateStr = dateStr;
      }
      groupsList.push({ type: 'message', message: msg, key: msg.id || msg.client_message_id });
    });

    return groupsList;
  }, [currentMessages]);

  // Empty state when no group is selected
  if (!selectedGroupId || !currentGroup) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-slate-50/60 p-6 text-center select-none">
        <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-4 shadow-xs">
          <MessageSquare size={32} />
        </div>
        <h2 className="text-lg font-bold text-slate-800">SmartInterview Group Chat</h2>
        <p className="text-xs text-slate-500 max-w-sm mt-1 leading-relaxed">
          Select a study group from the left panel to collaborate, challenge peers to adaptive interviews, and celebrate published results.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F0F2F5]/40 relative overflow-hidden">
      {/* ── Top Header ────────────────────────────────────────── */}
      <div className="h-16 bg-white border-b border-slate-200 px-4 flex items-center justify-between flex-shrink-0 z-10 shadow-xs">
        <div className="flex items-center gap-3 min-w-0">
          {/* Mobile Back Button */}
          {onBack && (
            <button
              onClick={onBack}
              className="md:hidden p-1.5 -ml-1 text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer border-none bg-transparent"
            >
              <ArrowLeft size={18} />
            </button>
          )}

          <div
            onClick={() => setDetailsModalOpen(true)}
            className="flex items-center gap-3 cursor-pointer group min-w-0"
          >
            <GroupAvatar name={currentGroup.name} size="md" />
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-slate-900 truncate group-hover:text-indigo-600 transition-colors">
                {currentGroup.name}
              </h2>
              <p className="text-xs text-slate-400 truncate">
                {typingText ? (
                  <span className="text-indigo-600 font-semibold animate-pulse">
                    {typingText}
                  </span>
                ) : (
                  <span>{currentGroup.members_count || currentGroup.members?.length || 1} members</span>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5">
          {isAdmin && (
            <button
              onClick={() => setShareModalOpen(true)}
              className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200/80 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Share2 size={14} />
              <span className="hidden sm:inline">Share Interview</span>
            </button>
          )}

          <button
            onClick={() => setDetailsModalOpen(true)}
            title="Group Information & Admin Settings"
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer border-none bg-transparent"
          >
            <Info size={19} />
          </button>
        </div>
      </div>

      {/* ── Disconnected Banner ───────────────────────────────── */}
      {wsStatus !== 'connected' && (
        <div className="bg-amber-500/10 border-b border-amber-200 px-4 py-1.5 text-center text-xs text-amber-800 font-medium flex items-center justify-center gap-1.5">
          <WifiOff size={13} />
          <span>
            {wsStatus === 'connecting'
              ? 'Reconnecting to real-time chat service...'
              : 'Offline. Reconnecting automatically...'}
          </span>
        </div>
      )}

      {/* ── Messages Container ─────────────────────────────────── */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-1 relative"
      >
        {/* Loading older spinner */}
        {loadingOlder && (
          <div className="flex justify-center py-2">
            <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Message Items with Date Dividers */}
        {groupedMessages.map((item) => {
          if (item.type === 'date') {
            return (
              <div key={item.key} className="flex justify-center my-4">
                <span className="bg-white/90 text-slate-500 text-[11px] font-semibold px-3 py-0.5 rounded-full shadow-xs border border-slate-200/60 uppercase tracking-wide">
                  {item.date}
                </span>
              </div>
            );
          }

          const isOwn = item.message.sender_id === user?.id;
          return (
            <ChatMessage
              key={item.key}
              message={item.message}
              isOwn={isOwn}
              showSender={!isOwn}
            />
          );
        })}

        {/* Typing indicator bubble */}
        {typingText && (
          <div className="flex items-center gap-2 mb-2 text-slate-400 text-xs">
            <div className="bg-white px-3.5 py-2 rounded-2xl rounded-tl-xs border border-slate-150 shadow-xs flex items-center gap-1.5">
              <span className="text-[11px] font-medium text-slate-500">{typingText}</span>
              <span className="flex gap-1 items-center ml-1">
                <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" />
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Scroll to bottom button */}
      {showScrollBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute right-6 bottom-20 p-2.5 bg-white text-indigo-600 rounded-full shadow-lg border border-slate-200 hover:bg-slate-50 transition-all cursor-pointer z-20 flex items-center justify-center animate-bounce"
        >
          <ChevronDown size={18} />
        </button>
      )}

      {/* ── Bottom Input ──────────────────────────────────────── */}
      <MessageInput
        groupId={selectedGroupId}
        isAdmin={isAdmin}
        onOpenShareInterview={() => setShareModalOpen(true)}
        disabled={wsStatus !== 'connected'}
      />

      {/* ── Modals ────────────────────────────────────────────── */}
      <ShareInterviewModal
        groupId={selectedGroupId}
        isOpen={shareModalOpen}
        onClose={() => setShareModalOpen(false)}
        onShared={() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }}
      />

      <GroupDetailsModal
        groupId={selectedGroupId}
        isOpen={detailsModalOpen}
        onClose={() => setDetailsModalOpen(false)}
      />
    </div>
  );
}
