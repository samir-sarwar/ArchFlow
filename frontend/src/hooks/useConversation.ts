import { useEffect, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import { useConversationStore } from '@/stores/conversationStore';
import { useDiagramStore } from '@/stores/diagramStore';
import { useUIStore } from '@/stores/uiStore';
import { createChunkPlayer, type AudioChunkPlayer } from '@/services/audio';
import { api } from '@/services/api';
import type { Message } from '@/types/conversation';

const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || '';

export function useConversation() {
  const { isConnected, lastMessage, sendMessage: wsSend } = useWebSocket(WS_URL);
  const conversationStore = useConversationStore();
  const updateDiagram = useDiagramStore((s) => s.updateDiagram);
  const restoreDiagram = useDiagramStore((s) => s.restoreDiagram);
  const { setLoading, setError } = useUIStore();
  const chunkPlayerRef = useRef<AudioChunkPlayer | null>(null);
  const responseTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  // Cleanup audio player on unmount
  useEffect(() => {
    return () => {
      chunkPlayerRef.current?.stop();
      clearTimeout(responseTimeoutRef.current);
    };
  }, []);

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

    // Skip empty frames (e.g. from Lambda returning no body)
    if (!lastMessage.data) return;

    try {
      const data = JSON.parse(lastMessage.data);

      if (data.type === 'voice_transcription') {
        conversationStore.updateLastUserMessage(data.payload.text);
      }

      if (data.type === 'voice_status') {
        conversationStore.setVoiceStatus({
          stage: data.payload.stage,
          message: data.payload.message,
        });
      }

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

        // Prepare audio player if response includes audio
        if (data.payload.hasAudio) {
          chunkPlayerRef.current?.stop();
          chunkPlayerRef.current = createChunkPlayer(24000, (playing) => {
            conversationStore.setAudioPlaying(playing);
          });
        }

        clearTimeout(responseTimeoutRef.current);
        conversationStore.setVoiceStatus(null);
        setLoading(false);
        setError(null);
      }

      if (data.type === 'audio_chunk') {
        chunkPlayerRef.current?.addChunk(data.payload.audio);
      }

      if (data.type === 'audio_end') {
        chunkPlayerRef.current?.finish();
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

      if (data.type === 'diagram_update') {
        if (data.payload?.diagram) {
          updateDiagram(data.payload.diagram, 'Diagram update');
        }
      }

      if (data.type === 'error') {
        console.error('[ArchFlow] Backend error:', data.payload);
        clearTimeout(responseTimeoutRef.current);
        conversationStore.setVoiceStatus(null);
        // Update any placeholder voice message to show it failed
        conversationStore.updateLastUserMessage('[Voice message failed]');
        setError(data.payload.message);
        setLoading(false);
      }
    } catch (err) {
      console.error('[ArchFlow] Failed to handle WebSocket message:', err, lastMessage?.data);
      clearTimeout(responseTimeoutRef.current);
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

  // Send a voice recording to the backend via S3 upload
  const sendVoiceMessage = async (audioBlob: Blob, mimeType?: string) => {
    const effectiveMime = mimeType || 'audio/webm;codecs=opus';
    console.log('[ArchFlow] Voice blob size:', audioBlob.size, 'mimeType:', effectiveMime);

    // Add placeholder user message immediately
    const userMsg: Message = {
      role: 'user',
      content: '[Voice message — transcribing...]',
      timestamp: new Date().toISOString(),
    };
    conversationStore.addMessage(userMsg);
    setLoading(true);
    setError(null);

    try {
      // 1. Get presigned URL from existing /upload endpoint
      const sessionId = conversationStore.sessionId || 'anonymous';
      const ext = effectiveMime.includes('mp4') ? 'mp4' : effectiveMime.includes('ogg') ? 'ogg' : 'webm';
      const fileName = `voice-${Date.now()}.${ext}`;
      const { uploadUrl, fileKey } = await api.uploadFile(
        sessionId,
        fileName,
        effectiveMime.split(';')[0], // strip codec info for MIME validation
        audioBlob.size,
      );
      console.log('[ArchFlow] Got presigned URL, uploading to S3:', fileKey);

      // 2. Upload raw audio blob directly to S3
      // Use the same stripped MIME type that was used to generate the presigned URL
      const strippedMime = effectiveMime.split(';')[0];
      const uploadResponse = await fetch(uploadUrl, {
        method: 'PUT',
        body: audioBlob,
        headers: { 'Content-Type': strippedMime },
      });
      if (!uploadResponse.ok) {
        throw new Error(`S3 upload failed: ${uploadResponse.status}`);
      }
      console.log('[ArchFlow] Audio uploaded to S3 successfully');

      // 3. Send lightweight WebSocket message with S3 key
      const currentDiagram = useDiagramStore.getState().currentSyntax;
      wsSend({
        action: 'voice',
        sessionId,
        audioKey: fileKey,
        mimeType: effectiveMime,
        currentDiagram: currentDiagram || undefined,
      });

      // 4. Timeout safety (90s for S3 download + Nova Sonic processing)
      clearTimeout(responseTimeoutRef.current);
      responseTimeoutRef.current = setTimeout(() => {
        setLoading(false);
        setError('Voice processing timed out. Please try again.');
      }, 90_000);
    } catch (err) {
      console.error('[ArchFlow] Voice upload failed:', err);
      setLoading(false);
      setError((err as Error).message || 'Voice upload failed. Please try again.');
    }
  };

  const stopAudioPlayback = () => {
    chunkPlayerRef.current?.stop();
  };

  return {
    messages: conversationStore.messages,
    sessionId: conversationStore.sessionId,
    isRecording: conversationStore.isRecording,
    isConnected,
    sendMessage,
    sendVoiceMessage,
    stopAudioPlayback,
    sendWsMessage: wsSend,
  };
}
