import { useEffect, useCallback, useRef } from 'react';
import { useDiagramStore } from '@/stores/diagramStore';
import { useCanvasStore } from '@/stores/canvasStore';
import { parseMermaidFlowchart } from '@/utils/mermaidParser';
import { generateMermaidFlowchart } from '@/utils/mermaidGenerator';

/**
 * Bridges canvasStore ↔ diagramStore.
 * - Parses Mermaid syntax into canvas state when entering manual mode
 * - Regenerates Mermaid from canvas state on every canvas edit
 * - Prevents infinite update loops via skipNextParse ref
 */
export function useCanvasSync() {
  const currentSyntax = useDiagramStore((s) => s.currentSyntax);
  const updateDiagram = useDiagramStore((s) => s.updateDiagram);
  const mode = useDiagramStore((s) => s.mode);

  const nodes = useCanvasStore((s) => s.nodes);
  const connections = useCanvasStore((s) => s.connections);
  const direction = useCanvasStore((s) => s.direction);
  const setCanvasState = useCanvasStore((s) => s.setCanvasState);

  // Prevent re-parsing syntax we just generated
  const skipNextParse = useRef(false);

  // Parse Mermaid → canvas when entering manual mode or syntax changes externally (undo/redo)
  useEffect(() => {
    if (mode !== 'manual') return;

    if (skipNextParse.current) {
      skipNextParse.current = false;
      return;
    }

    const parsed = parseMermaidFlowchart(currentSyntax);
    setCanvasState(parsed.nodes, parsed.connections, parsed.direction);
  }, [currentSyntax, mode, setCanvasState]);

  // Generate Mermaid from canvas state and push to diagram store
  const syncToMermaid = useCallback(() => {
    const syntax = generateMermaidFlowchart(nodes, connections, direction);
    skipNextParse.current = true;
    updateDiagram(syntax, 'Manual edit');
  }, [nodes, connections, direction, updateDiagram]);

  return { syncToMermaid };
}
