/**
 * Chat — Main page component for Group Chat & Real-Time Collaboration.
 * WhatsApp Web / Slack styled dual-panel layout with responsive mobile support.
 */

import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChat } from '../context/ChatContext';
import GroupList from '../components/chat/GroupList';
import ChatArea from '../components/chat/ChatArea';

export default function Chat() {
  const { groupId: routeGroupId } = useParams();
  const navigate = useNavigate();
  const { selectedGroupId, selectGroup } = useChat();

  // Sync route param with ChatContext if provided
  useEffect(() => {
    if (routeGroupId && Number(routeGroupId) !== selectedGroupId) {
      selectGroup(Number(routeGroupId));
    }
  }, [routeGroupId, selectedGroupId, selectGroup]);

  const handleSelectGroup = (id) => {
    selectGroup(id);
    navigate(`/chat/${id}`, { replace: true });
  };

  const handleBackToGroupList = () => {
    selectGroup(null);
    navigate('/chat', { replace: true });
  };

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col overflow-hidden bg-white">
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: Group List */}
        <div
          className={`w-full md:w-80 lg:w-96 flex-shrink-0 h-full border-r border-slate-200 ${
            selectedGroupId ? 'hidden md:flex' : 'flex'
          }`}
        >
          <GroupList onSelectGroup={handleSelectGroup} />
        </div>

        {/* Right Panel: Chat Conversation Area */}
        <div
          className={`flex-1 h-full ${
            !selectedGroupId ? 'hidden md:flex' : 'flex'
          }`}
        >
          <ChatArea onBack={handleBackToGroupList} />
        </div>
      </div>
    </div>
  );
}
