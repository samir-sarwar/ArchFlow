import { create } from 'zustand';
import type { Message } from '@/types/conversation';

interface ConversationStore {
  sessionId: string | null;
  messages: Message[];
  isRecording: boolean;
  currentTranscript: string;

  setSessionId: (id: string) => void;
  addMessage: (message: Message) => void;
  updateLastUserMessage: (content: string) => void;
  setRecording: (isRecording: boolean) => void;
  setTranscript: (transcript: string) => void;
  clearMessages: () => void;
}

export const useConversationStore = create<ConversationStore>((set) => ({
  sessionId: null,
  messages: [],
  isRecording: false,
  currentTranscript: '',

  setSessionId: (id) => set({ sessionId: id }),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  updateLastUserMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          messages[i] = { ...messages[i], content };
          break;
        }
      }
      return { messages };
    }),

  setRecording: (isRecording) => set({ isRecording }),

  setTranscript: (transcript) => set({ currentTranscript: transcript }),

  clearMessages: () => set({ messages: [], currentTranscript: '' }),
}));
