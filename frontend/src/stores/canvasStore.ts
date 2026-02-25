import { create } from 'zustand';
import type { CanvasNode, CanvasConnection } from '@/types/diagram';

interface CanvasStore {
  nodes: CanvasNode[];
  connections: CanvasConnection[];
  selectedNodeId: string | null;
  selectedConnectionId: string | null;
  connectingFrom: string | null;
  direction: 'TD' | 'LR';
  nodeCounter: number;

  setCanvasState: (
    nodes: CanvasNode[],
    connections: CanvasConnection[],
    direction: 'TD' | 'LR'
  ) => void;
  moveNode: (id: string, position: { x: number; y: number }) => void;
  updateNodeLabel: (id: string, label: string) => void;
  addNode: (node: CanvasNode) => void;
  removeNode: (id: string) => void;
  addConnection: (conn: CanvasConnection) => void;
  removeConnection: (id: string) => void;
  selectNode: (id: string | null) => void;
  selectConnection: (id: string | null) => void;
  startConnecting: (nodeId: string) => void;
  finishConnecting: (targetId: string) => CanvasConnection | null;
  cancelConnecting: () => void;
}

export const useCanvasStore = create<CanvasStore>((set, get) => ({
  nodes: [],
  connections: [],
  selectedNodeId: null,
  selectedConnectionId: null,
  connectingFrom: null,
  direction: 'TD',
  nodeCounter: 0,

  setCanvasState: (nodes, connections, direction) =>
    set({
      nodes,
      connections,
      direction,
      selectedNodeId: null,
      selectedConnectionId: null,
      connectingFrom: null,
      nodeCounter: nodes.length,
    }),

  moveNode: (id, position) =>
    set((state) => ({
      nodes: state.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
    })),

  updateNodeLabel: (id, label) =>
    set((state) => ({
      nodes: state.nodes.map((n) => (n.id === id ? { ...n, label } : n)),
    })),

  addNode: (node) =>
    set((state) => ({
      nodes: [...state.nodes, node],
      nodeCounter: state.nodeCounter + 1,
    })),

  removeNode: (id) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      connections: state.connections.filter(
        (c) => c.sourceId !== id && c.targetId !== id
      ),
      selectedNodeId:
        state.selectedNodeId === id ? null : state.selectedNodeId,
    })),

  addConnection: (conn) =>
    set((state) => ({
      connections: [...state.connections, conn],
      connectingFrom: null,
    })),

  removeConnection: (id) =>
    set((state) => ({
      connections: state.connections.filter((c) => c.id !== id),
      selectedConnectionId:
        state.selectedConnectionId === id ? null : state.selectedConnectionId,
    })),

  selectNode: (id) =>
    set({ selectedNodeId: id, selectedConnectionId: null }),

  selectConnection: (id) =>
    set({ selectedConnectionId: id, selectedNodeId: null }),

  startConnecting: (nodeId) => set({ connectingFrom: nodeId }),

  finishConnecting: (targetId) => {
    const { connectingFrom, connections } = get();
    if (!connectingFrom || connectingFrom === targetId) {
      set({ connectingFrom: null });
      return null;
    }

    // Check for duplicate
    const exists = connections.some(
      (c) => c.sourceId === connectingFrom && c.targetId === targetId
    );
    if (exists) {
      set({ connectingFrom: null });
      return null;
    }

    const newConn: CanvasConnection = {
      id: `${connectingFrom}-${targetId}`,
      sourceId: connectingFrom,
      targetId,
    };

    set((state) => ({
      connections: [...state.connections, newConn],
      connectingFrom: null,
    }));

    return newConn;
  },

  cancelConnecting: () => set({ connectingFrom: null }),
}));
