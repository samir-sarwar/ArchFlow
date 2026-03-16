import { useState, useCallback, useEffect } from 'react';
import { api } from '@/services/api';
import { useConversationStore } from '@/stores/conversationStore';
import { generateId } from '@/utils/generateId';

interface UploadedFile {
  name: string;
  size: number;
  type: string;
  status: 'uploading' | 'processing' | 'ready' | 'error';
  fileKey?: string;
  error?: string;
}

export function useFileUpload(sendWsMessage?: (msg: unknown) => void) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const sessionId = useConversationStore((s) => s.sessionId);

  const uploadFile = useCallback(
    async (file: File) => {
      // Auto-create session if none exists (allows uploading before first message)
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        currentSessionId = generateId();
        useConversationStore.getState().setSessionId(currentSessionId);
        sendWsMessage?.({
          action: 'restore_session',
          sessionId: currentSessionId,
        });
      }

      // Add file with uploading status
      const fileEntry: UploadedFile = {
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'uploading',
      };
      setFiles((prev) => [...prev, fileEntry]);

      try {
        // 1. Get presigned URL from backend
        const { uploadUrl, fileKey } = await api.uploadFile(
          currentSessionId,
          file.name,
          file.type,
          file.size
        );

        // 2. Upload directly to S3
        const uploadResponse = await fetch(uploadUrl, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type },
        });

        if (!uploadResponse.ok) {
          throw new Error(`Upload failed: ${uploadResponse.status}`);
        }

        // 3. Update status to processing
        setFiles((prev) =>
          prev.map((f) =>
            f.name === file.name ? { ...f, status: 'processing', fileKey } : f
          )
        );

        // 4. Notify backend via WebSocket to start analysis
        sendWsMessage?.({
          action: 'file_uploaded',
          sessionId: currentSessionId,
          fileKey,
          fileName: file.name,
          contentType: file.type,
          token: localStorage.getItem('archflow_token'),
        });
      } catch (err) {
        setFiles((prev) =>
          prev.map((f) =>
            f.name === file.name
              ? { ...f, status: 'error', error: (err as Error).message }
              : f
          )
        );
      }
    },
    [sessionId, sendWsMessage]
  );

  const updateFileStatus = useCallback(
    (fileKey: string, status: UploadedFile['status']) => {
      setFiles((prev) =>
        prev.map((f) => (f.fileKey === fileKey ? { ...f, status } : f))
      );
    },
    []
  );

  const removeFile = useCallback((fileName: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== fileName));
  }, []);

  // Listen for file-ready events dispatched by useConversation when backend analysis completes
  useEffect(() => {
    const handler = (e: Event) => {
      const { fileKey } = (e as CustomEvent<{ fileKey: string }>).detail;
      if (fileKey) updateFileStatus(fileKey, 'ready');
    };
    window.addEventListener('archflow:file-ready', handler);
    return () => window.removeEventListener('archflow:file-ready', handler);
  }, [updateFileStatus]);

  return { files, uploadFile, removeFile, updateFileStatus };
}
