import { VoiceInterface } from '@/components/VoiceInterface';
import { DiagramCanvas } from '@/components/DiagramCanvas';
import { useUIStore } from '@/stores/uiStore';
import { useConversationStore } from '@/stores/conversationStore';
import { Toast } from '@/components/shared/Toast';
import { RotateCcw } from 'lucide-react';

export default function App() {

  const notifications = useUIStore((s) => s.notifications);
  const removeNotification = useUIStore((s) => s.removeNotification);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Panel - Conversation */}
      <aside className="w-96 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <header className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">ArchFlow</h1>
            <p className="text-sm text-gray-500">Design systems by conversation</p>
          </div>
          <button
            onClick={() => {
              useConversationStore.getState().resetSession();
              // Refresh the page to reload state and websockets freshly
              window.location.reload();
            }}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
            title="Start New Chat"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </header>
        <VoiceInterface />
      </aside>

      {/* Right Panel - Diagram */}
      <main className="flex-1 flex flex-col">
        <DiagramCanvas />
      </main>

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
