const API_URL = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Request failed: ${response.status}`);
  }

  return response.json();
}

export const api = {
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
