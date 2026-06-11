'use client';

import React from 'react';
import { ChatInterface } from '@/components/copilot/ChatInterface';
import { SourcePanel } from '@/components/copilot/SourcePanel';
import { useCopilotStore } from '@/stores/copilot';

export default function CopilotPage() {
  const { messages } = useCopilotStore();
  
  // Find the last assistant message to display its sources
  const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Main Chat Area */}
      <div className="flex-1 min-w-0">
        <ChatInterface />
      </div>
      
      {/* Right Sidebar for Sources */}
      <div className="w-96 flex-shrink-0 hidden lg:block">
        <SourcePanel message={lastAssistantMessage} />
      </div>
    </div>
  );
}
