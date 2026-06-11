import React, { useState, useRef, useEffect } from 'react';
import { useCopilotStore } from '@/stores/copilot';
import { useCopilotWebSocket } from '@/hooks/useCopilotWebSocket';
import { MessageBubble } from './MessageBubble';
import { Send, Loader2 } from 'lucide-react';

export function ChatInterface() {
  const [input, setInput] = useState('');
  const { messages, isStreaming, streamBuffer, sessionId, addMessage } = useCopilotStore();
  const { sendQuery, isConnected } = useCopilotWebSocket();
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to bottom when messages or stream changes
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamBuffer]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming || !isConnected) return;

    const userMessage = {
      id: Math.random().toString(36).substring(7),
      role: 'user' as const,
      content: input,
    };
    
    addMessage(userMessage);
    sendQuery(input, sessionId);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Foundry Copilot</h2>
          <p className="text-xs text-zinc-400">
            {isConnected ? 'Connected to Intelligence Node' : 'Connecting...'}
          </p>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500">
            <p className="text-lg mb-2 text-zinc-300">How can I help you today?</p>
            <p className="text-sm text-center max-w-md">
              Ask about equipment status, standard operating procedures, failure history, or safety compliance.
            </p>
          </div>
        )}
        
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        
        {isStreaming && (
          <MessageBubble 
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamBuffer || 'Thinking...'
            }} 
          />
        )}
        <div ref={endOfMessagesRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-zinc-900 border-t border-zinc-800">
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!isConnected || isStreaming}
            placeholder={isConnected ? "Ask Copilot a question..." : "Connecting..."}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-full py-3 pl-4 pr-12 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || !isConnected || isStreaming}
            className="absolute right-2 p-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-full transition-colors"
          >
            {isStreaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </form>
      </div>
    </div>
  );
}
