import { create } from 'zustand';
import type { Message } from '@/types/conversation';

interface VoiceStatus {
  stage: string;
  message: string;
}

interface ConversationStore {
  sessionId: string | null;
  messages: Message[];
  isRecording: boolean;
  isAudioPlaying: boolean;
  currentTranscript: string;
  voiceStatus: VoiceStatus | null;
  _wsSend: ((msg: unknown) => void) | null;
  _isConnected: boolean;

  setSessionId: (id: string) => void;
  addMessage: (message: Message) => void;
  updateLastUserMessage: (content: string) => void;
  setRecording: (isRecording: boolean) => void;
  setAudioPlaying: (playing: boolean) => void;
  setTranscript: (transcript: string) => void;
  setVoiceStatus: (status: VoiceStatus | null) => void;
  clearMessages: () => void;
  setWsSend: (fn: (msg: unknown) => void) => void;
  setIsConnected: (connected: boolean) => void;
  restoreSession: (data: { messages: Message[]; sessionId: string }) => void;
}

export const useConversationStore = create<ConversationStore>((set) => ({
  sessionId: localStorage.getItem('archflow_sessionId'),
  messages: [],
  isRecording: false,
  isAudioPlaying: false,
  currentTranscript: '',
  voiceStatus: null,
  _wsSend: null,
  _isConnected: false,

  setSessionId: (id) => {
    localStorage.setItem('archflow_sessionId', id);
    set({ sessionId: id });
  },

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

  setAudioPlaying: (playing) => set({ isAudioPlaying: playing }),

  setTranscript: (transcript) => set({ currentTranscript: transcript }),

  setVoiceStatus: (status) => set({ voiceStatus: status }),

  clearMessages: () => set({ messages: [], currentTranscript: '', voiceStatus: null }),

  setWsSend: (fn) => set({ _wsSend: fn }),

  setIsConnected: (connected) => set({ _isConnected: connected }),

  restoreSession: ({ messages, sessionId }) => {
    localStorage.setItem('archflow_sessionId', sessionId);
    set({ messages, sessionId });
  },
}));
