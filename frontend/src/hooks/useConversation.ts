import { useConversationStore } from '@/stores/conversationStore';
import type { Message } from '@/types/conversation';

export function useConversation() {
  const store = useConversationStore();

  const sendMessage = (content: string) => {
    const message: Message = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    store.addMessage(message);
    // TODO: Send to backend via WebSocket
  };

  return {
    messages: store.messages,
    sessionId: store.sessionId,
    isRecording: store.isRecording,
    sendMessage,
  };
}
