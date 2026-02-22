import { create } from 'zustand';
import type { Message } from '@/types/conversation';

interface ConversationStore {
  sessionId: string | null;
  messages: Message[];
  isRecording: boolean;
  currentTranscript: string;

  setSessionId: (id: string) => void;
  addMessage: (message: Message) => void;
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

  setRecording: (isRecording) => set({ isRecording }),

  setTranscript: (transcript) => set({ currentTranscript: transcript }),

  clearMessages: () => set({ messages: [], currentTranscript: '' }),
}));
