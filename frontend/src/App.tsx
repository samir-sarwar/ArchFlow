import { VoiceInterface } from '@/components/VoiceInterface';
import { DiagramCanvas } from '@/components/DiagramCanvas';
import { useDiagramSync } from '@/hooks/useDiagramSync';
import { useUIStore } from '@/stores/uiStore';
import { Toast } from '@/components/shared/Toast';

export default function App() {
  useDiagramSync();

  const notifications = useUIStore((s) => s.notifications);
  const removeNotification = useUIStore((s) => s.removeNotification);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Left Panel - Conversation */}
      <aside className="w-96 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col">
        <header className="px-4 py-3 border-b border-gray-200">
          <h1 className="text-lg font-semibold text-gray-900">ArchFlow</h1>
          <p className="text-sm text-gray-500">Design systems by conversation</p>
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
