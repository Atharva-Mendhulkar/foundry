import { useEffect, useRef, useState } from 'react';
import { useCopilotStore } from '@/stores/copilot';

export function useCopilotWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const { appendStream, commitStream } = useCopilotStore();
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Determine the WS URL (handling local dev vs production)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use the backend docker port mapped to localhost
    const host = window.location.hostname;
    // Hardcoding to port 8008 since backend is on 8008 in our setup
    const wsUrl = `${protocol}//${host}:8008/api/v1/copilot/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('Copilot WS connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'token') {
          appendStream(data.content);
        } else if (data.type === 'sources') {
          // Temporarily store sources, will commit on 'complete'
          (ws as any)._lastSources = data.sources;
        } else if (data.type === 'complete') {
          commitStream((ws as any)._lastSources, data.latency_ms);
          (ws as any)._lastSources = null;
        } else if (data.type === 'error') {
          console.error('WS Error from server:', data.message);
          commitStream(); // Commit what we have
        }
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onclose = () => {
      console.log('Copilot WS disconnected');
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [appendStream, commitStream]);

  const sendQuery = (query: string, sessionId: string, equipmentContext?: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        query,
        session_id: sessionId,
        equipment_context: equipmentContext
      }));
    } else {
      console.error('WebSocket is not connected');
    }
  };

  return { sendQuery, isConnected };
}
