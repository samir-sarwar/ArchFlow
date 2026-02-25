import { useEffect } from 'react';
import { useWebSocket } from './useWebSocket';
import { useConversationStore } from '@/stores/conversationStore';
import { useDiagramStore } from '@/stores/diagramStore';
import { useUIStore } from '@/stores/uiStore';
import type { Message } from '@/types/conversation';

const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || '';

export function useConversation() {
  const { isConnected, lastMessage, sendMessage: wsSend } = useWebSocket(WS_URL);
  const conversationStore = useConversationStore();
  const updateDiagram = useDiagramStore((s) => s.updateDiagram);
  const restoreDiagram = useDiagramStore((s) => s.restoreDiagram);
  const { setLoading, setError } = useUIStore();

  // Share WebSocket send function and connection state via store
  useEffect(() => {
    conversationStore.setWsSend(wsSend);
  }, [wsSend]);

  useEffect(() => {
    conversationStore.setIsConnected(isConnected);
  }, [isConnected]);

  // Restore session on reconnect if sessionId exists
  useEffect(() => {
    if (!isConnected) return;
    const savedSessionId = localStorage.getItem('archflow_sessionId');
    if (savedSessionId) {
      wsSend({
        action: 'restore_session',
        sessionId: savedSessionId,
      });
      setLoading(true);
    }
  }, [isConnected]);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const data = JSON.parse(lastMessage.data);

      if (data.type === 'ai_response') {
        // Capture sessionId from first backend response
        if (data.sessionId) {
          conversationStore.setSessionId(data.sessionId);
        }

        // If voice transcription came back, update placeholder message
        if (data.payload.transcription) {
          conversationStore.updateLastUserMessage(data.payload.transcription);
        }

        // Add assistant message to conversation
        const assistantMsg: Message = {
          role: 'assistant',
          content: data.payload.text,
          timestamp: new Date().toISOString(),
          agent: data.payload.agent,
        };
        conversationStore.addMessage(assistantMsg);

        // Update diagram if backend included one
        if (data.payload.diagram) {
          updateDiagram(data.payload.diagram, data.payload.text);
        }

        setLoading(false);
        setError(null);
      }

      if (data.type === 'session_restored') {
        conversationStore.restoreSession({
          messages: data.payload.messages,
          sessionId: data.sessionId,
        });

        if (data.payload.currentDiagram) {
          restoreDiagram(
            data.payload.currentDiagram,
            data.payload.diagramVersions || []
          );
        }

        setLoading(false);
      }

      if (data.type === 'session_expired') {
        localStorage.removeItem('archflow_sessionId');
        conversationStore.clearMessages();
        setLoading(false);
      }

      if (data.type === 'file_status') {
        // File processing status update — handled by useFileUpload via callback
        if (data.payload.status === 'error') {
          setError(data.payload.message || 'File processing failed');
        }
      }

      if (data.type === 'file_analysis') {
        // File analysis complete — add result to conversation
        const analysisMsg: Message = {
          role: 'assistant',
          content: `**File analyzed: ${data.payload.fileName || 'document'}**\n\n${data.payload.summary || 'Analysis complete.'}`,
          timestamp: new Date().toISOString(),
          agent: 'context_analyzer',
        };
        conversationStore.addMessage(analysisMsg);

        // If the analysis included a diagram update
        if (data.payload.diagram) {
          updateDiagram(data.payload.diagram, 'Generated from uploaded file');
        }

        setLoading(false);
      }

      if (data.type === 'error') {
        setError(data.payload.message);
        setLoading(false);
      }
    } catch {
      setError('Failed to parse server response');
      setLoading(false);
    }
  }, [lastMessage]);

  // Send a text message to the backend
  const sendMessage = (content: string) => {
    if (!content.trim()) return;

    // Add user message to local store immediately
    const userMsg: Message = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    conversationStore.addMessage(userMsg);

    // Include current diagram so AI always has latest state
    const currentDiagram = useDiagramStore.getState().currentSyntax;

    // Send to backend via WebSocket
    wsSend({
      action: 'message',
      sessionId: conversationStore.sessionId,
      text: content,
      currentDiagram: currentDiagram || undefined,
    });

    setLoading(true);
    setError(null);
  };

  // Send a voice recording to the backend
  const sendVoiceMessage = async (audioBlob: Blob) => {
    const arrayBuffer = await audioBlob.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const base64 = btoa(binary);

    // Add placeholder user message
    const userMsg: Message = {
      role: 'user',
      content: '[Voice message — transcribing...]',
      timestamp: new Date().toISOString(),
    };
    conversationStore.addMessage(userMsg);

    // Include current diagram so AI always has latest state
    const currentDiagram = useDiagramStore.getState().currentSyntax;

    // Send voice action via WebSocket
    wsSend({
      action: 'voice',
      sessionId: conversationStore.sessionId,
      audio: base64,
      currentDiagram: currentDiagram || undefined,
    });

    setLoading(true);
    setError(null);
  };

  return {
    messages: conversationStore.messages,
    sessionId: conversationStore.sessionId,
    isRecording: conversationStore.isRecording,
    isConnected,
    sendMessage,
    sendVoiceMessage,
    sendWsMessage: wsSend,
  };
}
