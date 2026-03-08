import { useEffect } from 'react';
import { DiagramCanvas } from '@/components/DiagramCanvas';
import { Sidebar } from '@/components/Sidebar';
import { TopControls } from '@/components/TopControls';
import { ChatOverlay } from '@/components/ChatOverlay';
import { InputBar } from '@/components/InputBar';
import { VoiceIndicator } from '@/components/VoiceIndicator';
import { useUIStore } from '@/stores/uiStore';
import { Toast } from '@/components/shared/Toast';
import { Dropzone } from '@/components/FileUpload';
import { useConversation } from '@/hooks/useConversation';
import { useFileUpload } from '@/hooks/useFileUpload';

export default function App() {
  const notifications = useUIStore((s) => s.notifications);
  const removeNotification = useUIStore((s) => s.removeNotification);
  const theme = useUIStore((s) => s.theme);
  const { sendWsMessage, isConnected } = useConversation();
  const { uploadFile } = useFileUpload(sendWsMessage);

  // Apply dark class to document root
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  const handleFilesSelected = (files: File[]) => {
    files.forEach(uploadFile);
  };

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-gray-50 dark:bg-surface-500">
      {/* Full-screen diagram canvas */}
      <div className="absolute inset-0">
        <DiagramCanvas />
      </div>

      {/* Drag-and-drop zone (invisible until file drag) */}
      <Dropzone
        onFilesSelected={handleFilesSelected}
        disabled={!isConnected}
        overlay
      />

      {/* Sidebar */}
      <Sidebar />

      {/* Top floating controls */}
      <TopControls />

      {/* Chat overlay */}
      <ChatOverlay />

      {/* Voice recording indicator */}
      <VoiceIndicator />

      {/* Input bar */}
      <InputBar />

      {/* Toast Notifications */}
      <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
        {notifications.map((n) => (
          <Toast
            key={n.id}
            message={n.message}
            type={n.type}
            onDismiss={() => removeNotification(n.id)}
          />
        ))}
      </div>
    </div>
  );
}
