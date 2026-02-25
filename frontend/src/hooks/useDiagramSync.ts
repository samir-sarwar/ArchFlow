import { useEffect, useRef } from 'react';
import { useDiagramStore } from '@/stores/diagramStore';
import { useConversationStore } from '@/stores/conversationStore';

const SYNC_DEBOUNCE_MS = 1000;

/**
 * Watches diagramStore.currentSyntax and debounce-syncs manual edits
 * to the backend via WebSocket. Mounted at the App level.
 *
 * Only syncs when mode === 'manual' — voice mode edits already persist
 * through the normal _process_message flow.
 */
export function useDiagramSync() {
  const currentSyntax = useDiagramStore((s) => s.currentSyntax);
  const mode = useDiagramStore((s) => s.mode);
  const sessionId = useConversationStore((s) => s.sessionId);
  const wsSend = useConversationStore((s) => s._wsSend);
  const isConnected = useConversationStore((s) => s._isConnected);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isRestoringRef = useRef(false);
  const prevSyntaxRef = useRef(currentSyntax);

  // Expose a way to mark the next change as a restore (skip sync)
  useEffect(() => {
    // On session_restored, diagramStore.currentSyntax changes but we
    // don't want to echo it back to the backend. Detect this by checking
    // if the change came from restoreDiagram (which sets history directly).
    // We use a subscribe to detect restoreDiagram calls.
    const unsub = useDiagramStore.subscribe((state, prevState) => {
      // restoreDiagram sets historyIndex from versions array, while
      // updateDiagram increments it by 1. If history changed dramatically,
      // it's a restore.
      if (
        state.history !== prevState.history &&
        state.history.length !== prevState.history.length + 1
      ) {
        isRestoringRef.current = true;
      }
    });
    return unsub;
  }, []);

  useEffect(() => {
    if (!isConnected || !sessionId || !currentSyntax || !wsSend) return;
    if (mode !== 'manual') return;

    // Skip if this change came from a session restore
    if (isRestoringRef.current) {
      isRestoringRef.current = false;
      prevSyntaxRef.current = currentSyntax;
      return;
    }

    // Skip if syntax hasn't actually changed
    if (currentSyntax === prevSyntaxRef.current) return;
    prevSyntaxRef.current = currentSyntax;

    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      wsSend({
        action: 'sync_diagram',
        sessionId,
        syntax: currentSyntax,
      });
    }, SYNC_DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [currentSyntax, mode, sessionId, isConnected, wsSend]);
}
