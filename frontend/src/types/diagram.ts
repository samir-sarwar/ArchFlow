export type DiagramType = 'flowchart' | 'sequence' | 'er' | 'c4';

export type EditorMode = 'voice' | 'manual';

export interface DiagramVersion {
  version: number;
  syntax: string;
  timestamp: string;
  description?: string;
}

export interface DiagramState {
  syntax: string;
  diagramType: DiagramType;
  isValid: boolean;
  errorMessage?: string;
}

// ── Canvas / Manual Editor types ──

export type NodeType = 'service' | 'database' | 'loadbalancer' | 'cache' | 'custom';

export interface CanvasNode {
  id: string;
  label: string;
  type: NodeType;
  position: { x: number; y: number };
}

export interface CanvasConnection {
  id: string;
  sourceId: string;
  targetId: string;
  label?: string;
}

export const DND_ITEM_TYPES = {
  LIBRARY_ELEMENT: 'library-element',
} as const;

export interface DraggedLibraryItem {
  type: NodeType;
  label: string;
}
