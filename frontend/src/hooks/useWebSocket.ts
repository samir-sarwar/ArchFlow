import { useState, useEffect, useCallback, useRef } from 'react';

const MAX_RECONNECT_DELAY = 10_000;
const INITIAL_RECONNECT_DELAY = 1_000;

export function useWebSocket(url: string, onMessage?: (event: MessageEvent) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const reconnectDelay = useRef(INITIAL_RECONNECT_DELAY);
  const mountedRef = useRef(true);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!url || !mountedRef.current) return;

    // Don't create a new connection if one is already open or connecting
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const ws = new WebSocket(url);

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }
      reconnectDelay.current = INITIAL_RECONNECT_DELAY;
      setIsConnected(true);
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      // Auto-reconnect with exponential backoff
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(
          reconnectDelay.current * 2,
          MAX_RECONNECT_DELAY,
        );
        connect();
      }, reconnectDelay.current);
    };

    ws.onmessage = (event) => {
      console.debug('[ArchFlow] WS recv', typeof event.data === 'string' ? event.data.length : '(binary)', 'bytes');
      // Call direct callback first (avoids React state batching dropping rapid messages)
      onMessageRef.current?.(event);
      setLastMessage(event);
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect logic is handled there
    };

    wsRef.current = ws;
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        if (wsRef.current.readyState === WebSocket.CONNECTING) {
          // Defer close until open to avoid "closed before established" browser warning
          // (triggered by React StrictMode's deliberate mount/unmount/remount cycle)
          const ws = wsRef.current;
          ws.onopen = () => ws.close();
        } else {
          wsRef.current.close();
        }
        wsRef.current = null;
      }
      setIsConnected(false);
    };
  }, [connect]);

  const sendMessage = useCallback((message: unknown): boolean => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[ArchFlow] WebSocket not open, dropping message');
      return false;
    }
    try {
      const payload = JSON.stringify(message);
      console.debug('[ArchFlow] WS send', payload.length, 'bytes');
      wsRef.current.send(payload);
      return true;
    } catch (err) {
      console.error('[ArchFlow] WebSocket send failed:', err);
      return false;
    }
  }, []);

  const sendBinary = useCallback((data: ArrayBuffer) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  return { isConnected, lastMessage, sendMessage, sendBinary };
}
