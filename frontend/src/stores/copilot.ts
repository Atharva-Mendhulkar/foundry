import { create } from 'zustand';

export interface Source {
  doc_id?: string;
  text?: string;
  doc_type?: string;
  [key: string]: any;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  latency_ms?: number;
}

interface CopilotState {
  messages: Message[];
  isStreaming: boolean;
  streamBuffer: string;
  sessionId: string;
  addMessage: (message: Message) => void;
  appendStream: (text: string) => void;
  commitStream: (sources?: Source[], latency_ms?: number) => void;
  clearMessages: () => void;
}

export const useCopilotStore = create<CopilotState>((set) => ({
  messages: [],
  isStreaming: false,
  streamBuffer: '',
  sessionId: Math.random().toString(36).substring(7),
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  
  appendStream: (text) => set((state) => ({
    isStreaming: true,
    streamBuffer: state.streamBuffer + text
  })),
  
  commitStream: (sources, latency_ms) => set((state) => {
    if (!state.streamBuffer) return state;
    
    const newMsg: Message = {
      id: Math.random().toString(36).substring(7),
      role: 'assistant',
      content: state.streamBuffer,
      sources,
      latency_ms
    };
    
    return {
      messages: [...state.messages, newMsg],
      isStreaming: false,
      streamBuffer: ''
    };
  }),
  
  clearMessages: () => set({ 
    messages: [], 
    sessionId: Math.random().toString(36).substring(7) 
  })
}));
