import { VoiceInterface } from '@/components/VoiceInterface';
import { DiagramCanvas } from '@/components/DiagramCanvas';
import { useDiagramSync } from '@/hooks/useDiagramSync';

export default function App() {
  useDiagramSync();

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
    </div>
  );
}
