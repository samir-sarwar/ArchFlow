const API_URL = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('archflow_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    headers,
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || error.message || `Request failed: ${response.status}`);
  }

  return response.json();
}

interface AuthResponse {
  token: string;
  user_id: string;
  email: string;
  display_name: string;
}

export const api = {
  signup: (email: string, password: string) =>
    request<AuthResponse>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  uploadFile: (sessionId: string, fileName: string, contentType: string, fileSize: number) =>
    request<{ uploadUrl: string; fileKey: string }>('/upload', {
      method: 'POST',
      body: JSON.stringify({ sessionId, fileName, contentType, fileSize }),
    }),

  exportDiagram: (sessionId: string, format: string) =>
    request('/export', {
      method: 'POST',
      body: JSON.stringify({ sessionId, format }),
    }),

  createShareLink: (sessionId: string) =>
    request<{ shareId: string }>('/share', {
      method: 'POST',
      body: JSON.stringify({ sessionId }),
    }),
};
