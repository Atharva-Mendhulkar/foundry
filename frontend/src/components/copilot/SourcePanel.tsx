import React from 'react';
import { Message } from '@/stores/copilot';
import { FileText, Database, Box } from 'lucide-react';

interface Props {
  message?: Message;
}

export function SourcePanel({ message }: Props) {
  if (!message || message.role !== 'assistant' || !message.sources || message.sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-zinc-500 p-6 text-center">
        <Database className="w-12 h-12 mb-4 text-zinc-700" />
        <p>No sources available for the current message.</p>
        <p className="text-sm mt-2">Ask a question to see the retrieved knowledge graph and vector context.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-zinc-900 border-l border-zinc-800 p-4 overflow-y-auto">
      <h3 className="text-lg font-semibold text-zinc-100 mb-4 flex items-center gap-2">
        <Box size={20} className="text-emerald-500" />
        Retrieval Context
      </h3>
      
      <div className="flex flex-col gap-4">
        {message.sources.map((source, idx) => (
          <div key={idx} className="bg-zinc-800 rounded-lg p-3 border border-zinc-700/50">
            <div className="flex items-center gap-2 mb-2 text-zinc-300 font-medium text-sm">
              <FileText size={16} className="text-indigo-400" />
              <span>{source.doc_type?.toUpperCase() || 'DOCUMENT'} - {source.doc_id?.substring(0,8)}</span>
            </div>
            <p className="text-sm text-zinc-400 line-clamp-4 leading-relaxed">
              {source.text}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
