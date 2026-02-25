import { useRef, useCallback, useEffect } from 'react';
import { useDrop } from 'react-dnd';
import { useCanvasStore } from '@/stores/canvasStore';
import { useCanvasSync } from '@/hooks/useCanvasSync';
import { NodeComponent } from './NodeComponent';
import { ConnectionLine } from './ConnectionLine';
import { DND_ITEM_TYPES } from '@/types/diagram';
import type { CanvasNode, DraggedLibraryItem, NodeType } from '@/types/diagram';

// ID prefix counters per type for readable Mermaid IDs
const TYPE_PREFIXES: Record<NodeType, string> = {
  service: 'svc',
  database: 'db',
  loadbalancer: 'lb',
  cache: 'cache',
  custom: 'node',
};

export function Canvas() {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const prevNodesRef = useRef<CanvasNode[]>([]);
  const prevConnsLen = useRef(0);

  const nodes = useCanvasStore((s) => s.nodes);
  const connections = useCanvasStore((s) => s.connections);
  const selectedNodeId = useCanvasStore((s) => s.selectedNodeId);
  const selectedConnectionId = useCanvasStore((s) => s.selectedConnectionId);
  const nodeCounter = useCanvasStore((s) => s.nodeCounter);
  const addNode = useCanvasStore((s) => s.addNode);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const selectConnection = useCanvasStore((s) => s.selectConnection);
  const cancelConnecting = useCanvasStore((s) => s.cancelConnecting);
  const removeNode = useCanvasStore((s) => s.removeNode);
  const removeConnection = useCanvasStore((s) => s.removeConnection);

  const { syncToMermaid } = useCanvasSync();

  // Drop target for library elements
  const [{ isOver }, dropRef] = useDrop(
    () => ({
      accept: DND_ITEM_TYPES.LIBRARY_ELEMENT,
      drop: (item: DraggedLibraryItem, monitor) => {
        const offset = monitor.getClientOffset();
        const canvasRect = canvasRef.current?.getBoundingClientRect();
        if (!offset || !canvasRect) return;

        const position = {
          x: offset.x - canvasRect.left + (canvasRef.current?.scrollLeft ?? 0),
          y: offset.y - canvasRect.top + (canvasRef.current?.scrollTop ?? 0),
        };

        const prefix = TYPE_PREFIXES[item.type] || 'node';
        const newNode: CanvasNode = {
          id: `${prefix}${nodeCounter + 1}`,
          label: item.label,
          type: item.type,
          position,
        };
        addNode(newNode);
      },
      collect: (monitor) => ({ isOver: monitor.isOver() }),
    }),
    [nodeCounter, addNode]
  );

  // Click on empty canvas = deselect
  const handleCanvasClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === canvasRef.current || e.target === canvasRef.current?.querySelector('svg')) {
        selectNode(null);
        selectConnection(null);
        cancelConnecting();
      }
    },
    [selectNode, selectConnection, cancelConnecting]
  );

  // Delete key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Don't delete if user is editing a label
        if (
          document.activeElement?.tagName === 'INPUT' ||
          document.activeElement?.tagName === 'TEXTAREA'
        ) {
          return;
        }
        if (selectedNodeId) {
          removeNode(selectedNodeId);
        } else if (selectedConnectionId) {
          removeConnection(selectedConnectionId);
        }
      }
      if (e.key === 'Escape') {
        cancelConnecting();
        selectNode(null);
        selectConnection(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNodeId, selectedConnectionId, removeNode, removeConnection, cancelConnecting, selectNode, selectConnection]);

  // Sync to Mermaid whenever nodes or connections change
  useEffect(() => {
    if (
      nodes !== prevNodesRef.current ||
      connections.length !== prevConnsLen.current
    ) {
      prevNodesRef.current = nodes;
      prevConnsLen.current = connections.length;
      syncToMermaid();
    }
  }, [nodes, connections, syncToMermaid]);

  // Combine refs for drop target and direct reference
  const setRefs = useCallback(
    (node: HTMLDivElement | null) => {
      canvasRef.current = node;
      dropRef(node);
    },
    [dropRef]
  );

  return (
    <div
      ref={setRefs}
      className={`relative w-full h-full overflow-auto ${
        isOver ? 'bg-blue-50' : 'bg-gray-50'
      }`}
      onClick={handleCanvasClick}
    >
      {/* SVG layer for connections */}
      <svg
        className="absolute inset-0 pointer-events-none"
        style={{ width: '100%', height: '100%', minWidth: 3000, minHeight: 2000 }}
      >
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="10"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af" />
          </marker>
        </defs>
        {connections.map((conn) => {
          const source = nodes.find((n) => n.id === conn.sourceId);
          const target = nodes.find((n) => n.id === conn.targetId);
          if (!source || !target) return null;
          return (
            <ConnectionLine
              key={conn.id}
              connection={conn}
              sourcePos={source.position}
              targetPos={target.position}
              isSelected={selectedConnectionId === conn.id}
              onSelect={() => selectConnection(conn.id)}
            />
          );
        })}
      </svg>

      {/* Node layer */}
      {nodes.map((node) => (
        <NodeComponent
          key={node.id}
          {...node}
          isSelected={selectedNodeId === node.id}
        />
      ))}

      {/* Empty state */}
      {nodes.length === 0 && (
        <div className="flex items-center justify-center h-full text-gray-400 pointer-events-none">
          <p className="text-sm">Drag elements from the sidebar to start building</p>
        </div>
      )}
    </div>
  );
}
