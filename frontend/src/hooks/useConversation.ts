import { useEffect } from 'react';
import { useWebSocket } from './useWebSocket';
import { useConversationStore } from '@/stores/conversationStore';
import { useDiagramStore } from '@/stores/diagramStore';
import { useUIStore } from '@/stores/uiStore';
import type { Message } from '@/types/conversation';

const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || '';

export function useConversation() {
  const { isConnected, lastMessage, sendMessage: wsSend } = useWebSocket(WS_URL);
  const conversationStore = useConversationStore();
  const updateDiagram = useDiagramStore((s) => s.updateDiagram);
  const { setLoading, setError } = useUIStore();

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const data = JSON.parse(lastMessage.data);

      if (data.type === 'ai_response') {
        // Capture sessionId from first backend response
        if (data.sessionId) {
          conversationStore.setSessionId(data.sessionId);
        }

        // Add assistant message to conversation
        const assistantMsg: Message = {
          role: 'assistant',
          content: data.payload.text,
          timestamp: new Date().toISOString(),
          agent: data.payload.agent,
        };
        conversationStore.addMessage(assistantMsg);

        // Update diagram if backend included one
        if (data.payload.diagram) {
          updateDiagram(data.payload.diagram, data.payload.text);
        }

        setLoading(false);
        setError(null);
      }

      if (data.type === 'error') {
        setError(data.payload.message);
        setLoading(false);
      }
    } catch {
      setError('Failed to parse server response');
      setLoading(false);
    }
  }, [lastMessage]);

  // Send a text message to the backend
  const sendMessage = (content: string) => {
    if (!content.trim()) return;

    // Add user message to local store immediately
    const userMsg: Message = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    conversationStore.addMessage(userMsg);

    // Send to backend via WebSocket
    wsSend({
      action: 'message',
      sessionId: conversationStore.sessionId,
      text: content,
    });

    setLoading(true);
    setError(null);
  };

  return {
    messages: conversationStore.messages,
    sessionId: conversationStore.sessionId,
    isRecording: conversationStore.isRecording,
    isConnected,
    sendMessage,
  };
}
