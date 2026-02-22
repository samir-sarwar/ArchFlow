const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || '';

export function createWebSocketConnection(sessionId: string): WebSocket {
  const url = `${WS_URL}?sessionId=${sessionId}`;
  return new WebSocket(url);
}
