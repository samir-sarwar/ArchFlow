import { useDiagramStore } from '@/stores/diagramStore';

export function DiagramControls() {
  const { undo, redo, historyIndex, history, mode, switchMode } =
    useDiagramStore();

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 bg-white">
      <button
        onClick={undo}
        disabled={historyIndex <= 0}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
      >
        Undo
      </button>
      <button
        onClick={redo}
        disabled={historyIndex >= history.length - 1}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
      >
        Redo
      </button>

      <div className="mx-2 h-4 w-px bg-gray-300" />

      <button
        onClick={() => switchMode(mode === 'voice' ? 'manual' : 'voice')}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50"
      >
        {mode === 'voice' ? 'Manual Mode' : 'Voice Mode'}
      </button>
    </div>
  );
}
