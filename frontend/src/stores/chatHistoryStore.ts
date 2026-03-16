import { create } from 'zustand';

export interface ChatSummary {
  session_id: string;
  title: string;
  last_activity: string;
  created_at: string;
  current_diagram?: string;
}

interface ChatHistoryStore {
  conversations: ChatSummary[];
  activeConversationId: string | null;

  setConversations: (convs: ChatSummary[]) => void;
  setActiveConversation: (id: string | null) => void;
  removeConversation: (id: string) => void;
  addOrUpdateConversation: (conv: ChatSummary) => void;
}

export const useChatHistoryStore = create<ChatHistoryStore>((set) => ({
  conversations: [],
  activeConversationId: null,

  setConversations: (conversations) => set({ conversations }),

  setActiveConversation: (id) => set({ activeConversationId: id }),

  removeConversation: (id) =>
    set((s) => ({
      conversations: s.conversations.filter((c) => c.session_id !== id),
      activeConversationId: s.activeConversationId === id ? null : s.activeConversationId,
    })),

  addOrUpdateConversation: (conv) =>
    set((s) => {
      const existing = s.conversations.findIndex((c) => c.session_id === conv.session_id);
      if (existing >= 0) {
        const updated = [...s.conversations];
        updated[existing] = conv;
        return { conversations: updated };
      }
      return { conversations: [conv, ...s.conversations] };
    }),
}));
