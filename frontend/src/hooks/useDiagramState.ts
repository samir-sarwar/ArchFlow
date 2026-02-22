import { useDiagramStore } from '@/stores/diagramStore';

export function useDiagramState() {
  const store = useDiagramStore();

  return {
    syntax: store.currentSyntax,
    mode: store.mode,
    canUndo: store.historyIndex > 0,
    canRedo: store.historyIndex < store.history.length - 1,
    versionCount: store.history.length,
    updateDiagram: store.updateDiagram,
    undo: store.undo,
    redo: store.redo,
    switchMode: store.switchMode,
  };
}
