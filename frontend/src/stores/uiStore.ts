import { create } from 'zustand';

interface Notification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

type Theme = 'light' | 'dark';
type ActiveView = 'preview' | 'code';

const getStoredTheme = (): Theme => {
  try {
    const stored = localStorage.getItem('archflow-theme');
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // localStorage unavailable
  }
  return 'light';
};

interface UIStore {
  isLoading: boolean;
  error: string | null;
  notifications: Notification[];
  sidebarOpen: boolean;
  chatOverlayOpen: boolean;
  theme: Theme;
  activeView: ActiveView;

  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addNotification: (message: string, type: Notification['type']) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleChatOverlay: () => void;
  setChatOverlayOpen: (open: boolean) => void;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setActiveView: (view: ActiveView) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  isLoading: false,
  error: null,
  notifications: [],
  sidebarOpen: true,
  chatOverlayOpen: true,
  theme: getStoredTheme(),
  activeView: 'preview',

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  addNotification: (message, type) =>
    set((state) => ({
      notifications: [
        ...state.notifications,
        { id: crypto.randomUUID(), message, type },
      ],
    })),

  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),

  clearNotifications: () => set({ notifications: [] }),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleChatOverlay: () =>
    set((state) => ({ chatOverlayOpen: !state.chatOverlayOpen })),
  setChatOverlayOpen: (open) => set({ chatOverlayOpen: open }),

  setTheme: (theme) => {
    try { localStorage.setItem('archflow-theme', theme); } catch {}
    document.documentElement.classList.toggle('dark', theme === 'dark');
    set({ theme });
  },
  toggleTheme: () =>
    set((state) => {
      const next = state.theme === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('archflow-theme', next); } catch {}
      document.documentElement.classList.toggle('dark', next === 'dark');
      return { theme: next };
    }),

  setActiveView: (view) => set({ activeView: view }),
}));
