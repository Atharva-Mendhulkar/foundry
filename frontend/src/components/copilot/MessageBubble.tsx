import React from 'react';
import { Message } from '@/stores/copilot';
import ReactMarkdown from 'react-markdown';
import { Bot, User } from 'lucide-react';

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`flex max-w-[80%] ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start gap-3`}>
        {/* Avatar */}
        <div className={`flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-full ${isUser ? 'bg-indigo-600' : 'bg-emerald-600'}`}>
          {isUser ? <User size={16} className="text-white" /> : <Bot size={16} className="text-white" />}
        </div>
        
        {/* Content */}
        <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
          <div className={`px-4 py-3 rounded-2xl ${
            isUser 
              ? 'bg-indigo-600 text-white rounded-tr-none' 
              : 'bg-zinc-800 border border-zinc-700 text-zinc-100 rounded-tl-none'
          }`}>
            <div className="prose prose-invert max-w-none prose-sm">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </div>
          
          {/* Metadata (Latency, Sources tag) */}
          {!isUser && message.latency_ms && (
            <div className="text-xs text-zinc-500 mt-1 ml-1 flex items-center gap-2">
              <span>{(message.latency_ms / 1000).toFixed(1)}s</span>
              {message.sources && message.sources.length > 0 && (
                <span className="text-emerald-500/70">{message.sources.length} sources cited</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
