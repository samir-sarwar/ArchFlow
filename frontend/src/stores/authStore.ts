import { create } from 'zustand';

function isTokenExpired(token: string): boolean {
  try {
    const payload = token.split('.')[1];
    if (!payload) return true;
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    if (!decoded.exp) return true;
    // 30s buffer to avoid race with server-side check
    return decoded.exp * 1000 < Date.now() - 30_000;
  } catch {
    return true;
  }
}

interface User {
  user_id: string;
  email: string;
  display_name: string;
}

interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;

  login: (token: string, user: User) => void;
  logout: () => void;
  loadFromStorage: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,

  login: (token, user) => {
    localStorage.setItem('archflow_token', token);
    localStorage.setItem('archflow_user', JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('archflow_token');
    localStorage.removeItem('archflow_user');
    localStorage.removeItem('archflow_sessionId');
    set({ token: null, user: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    const token = localStorage.getItem('archflow_token');
    const userJson = localStorage.getItem('archflow_user');
    if (token && userJson) {
      if (isTokenExpired(token)) {
        localStorage.removeItem('archflow_token');
        localStorage.removeItem('archflow_user');
        localStorage.removeItem('archflow_sessionId');
        set({ token: null, user: null, isAuthenticated: false });
        return;
      }
      try {
        const user = JSON.parse(userJson);
        set({ token, user, isAuthenticated: true });
      } catch {
        set({ token: null, user: null, isAuthenticated: false });
      }
    }
  },
}));
