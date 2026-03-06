import { create } from 'zustand';
import type { DiagramVersion } from '@/types/diagram';

const MAX_HISTORY = 10;

interface DiagramStore {
  currentSyntax: string;
  renderedSvg: string;
  history: DiagramVersion[];
  historyIndex: number;

  updateDiagram: (syntax: string, description?: string) => void;
  restoreDiagram: (syntax: string, versions: DiagramVersion[]) => void;
  undo: () => void;
  redo: () => void;
  clearDiagram: () => void;
  setRenderedSvg: (svg: string) => void;
}

export const useDiagramStore = create<DiagramStore>((set, get) => ({
  currentSyntax: '',
  renderedSvg: '',
  history: [],
  historyIndex: -1,

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

  restoreDiagram: (syntax, versions) =>
    set({
      currentSyntax: syntax,
      history: versions.slice(-MAX_HISTORY),
      historyIndex: Math.min(versions.length, MAX_HISTORY) - 1,
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

  clearDiagram: () =>
    set({ currentSyntax: '', renderedSvg: '', history: [], historyIndex: -1 }),

  setRenderedSvg: (svg) => set({ renderedSvg: svg }),
}));
