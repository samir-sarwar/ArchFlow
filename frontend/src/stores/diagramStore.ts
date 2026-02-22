import { create } from 'zustand';
import type { DiagramVersion, EditorMode } from '@/types/diagram';

const MAX_HISTORY = 10;

interface DiagramStore {
  currentSyntax: string;
  history: DiagramVersion[];
  historyIndex: number;
  mode: EditorMode;

  updateDiagram: (syntax: string, description?: string) => void;
  undo: () => void;
  redo: () => void;
  switchMode: (mode: EditorMode) => void;
  clearDiagram: () => void;
}

export const useDiagramStore = create<DiagramStore>((set, get) => ({
  currentSyntax: '',
  history: [],
  historyIndex: -1,
  mode: 'voice',

  updateDiagram: (syntax, description) =>
    set((state) => {
      const newVersion: DiagramVersion = {
        version: state.history.length + 1,
        syntax,
        timestamp: new Date().toISOString(),
        description,
      };

      const trimmedHistory = state.history.slice(0, state.historyIndex + 1);
      const newHistory = [...trimmedHistory, newVersion].slice(-MAX_HISTORY);

      return {
        currentSyntax: syntax,
        history: newHistory,
        historyIndex: newHistory.length - 1,
      };
    }),

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex > 0) {
      const prevIndex = historyIndex - 1;
      set({
        currentSyntax: history[prevIndex].syntax,
        historyIndex: prevIndex,
      });
    }
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex < history.length - 1) {
      const nextIndex = historyIndex + 1;
      set({
        currentSyntax: history[nextIndex].syntax,
        historyIndex: nextIndex,
      });
    }
  },

  switchMode: (mode) => set({ mode }),

  clearDiagram: () =>
    set({ currentSyntax: '', history: [], historyIndex: -1 }),
}));
