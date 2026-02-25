import { useState, useRef, useCallback } from 'react';
import { useCanvasStore } from '@/stores/canvasStore';
import type { NodeType } from '@/types/diagram';
import { Server, Database, Globe, HardDrive, type LucideIcon } from 'lucide-react';

interface NodeComponentProps {
  id: string;
  label: string;
  type: NodeType;
  position: { x: number; y: number };
  isSelected?: boolean;
}

const NODE_ICONS: Record<NodeType, LucideIcon> = {
  service: Server,
  database: Database,
  loadbalancer: Globe,
  cache: HardDrive,
  custom: Server,
};

const NODE_STYLES: Record<NodeType, string> = {
  service: 'bg-blue-50 border-blue-300',
  database: 'bg-green-50 border-green-300',
  loadbalancer: 'bg-orange-50 border-orange-300',
  cache: 'bg-purple-50 border-purple-300',
  custom: 'bg-gray-50 border-gray-300',
};

export function NodeComponent({
  id,
  label,
  type,
  position,
  isSelected,
}: NodeComponentProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(label);
  const inputRef = useRef<HTMLInputElement>(null);

  const moveNode = useCanvasStore((s) => s.moveNode);
  const selectNode = useCanvasStore((s) => s.selectNode);
  const updateNodeLabel = useCanvasStore((s) => s.updateNodeLabel);
  const startConnecting = useCanvasStore((s) => s.startConnecting);
  const finishConnecting = useCanvasStore((s) => s.finishConnecting);
  const connectingFrom = useCanvasStore((s) => s.connectingFrom);

  const Icon = NODE_ICONS[type] || Server;

  // Drag to reposition (native mouse events to avoid react-dnd conflict)
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Ignore if clicking a port or editing
      if ((e.target as HTMLElement).dataset.port || isEditing) return;
      e.stopPropagation();
      selectNode(id);

      const startX = e.clientX;
      const startY = e.clientY;
      const startPos = { ...position };

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const dx = moveEvent.clientX - startX;
        const dy = moveEvent.clientY - startY;
        moveNode(id, {
          x: Math.max(0, startPos.x + dx),
          y: Math.max(0, startPos.y + dy),
        });
      };

      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [id, position, moveNode, selectNode, isEditing]
  );

  // Double-click to edit label
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsEditing(true);
      setEditValue(label);
      setTimeout(() => inputRef.current?.select(), 0);
    },
    [label]
  );

  const handleLabelSubmit = useCallback(() => {
    if (editValue.trim()) {
      updateNodeLabel(id, editValue.trim());
    }
    setIsEditing(false);
  }, [id, editValue, updateNodeLabel]);

  const handleLabelKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') handleLabelSubmit();
      if (e.key === 'Escape') setIsEditing(false);
    },
    [handleLabelSubmit]
  );

  // Connection ports
  const handleOutputClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      startConnecting(id);
    },
    [id, startConnecting]
  );

  const handleInputClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (connectingFrom && connectingFrom !== id) {
        finishConnecting(id);
      }
    },
    [id, connectingFrom, finishConnecting]
  );

  return (
    <div
      className={`absolute select-none ${
        isEditing ? 'cursor-text' : connectingFrom ? 'cursor-crosshair' : 'cursor-move'
      } ${NODE_STYLES[type]} border-2 p-3 min-w-[120px] text-center rounded-lg shadow-sm ${
        isSelected ? 'ring-2 ring-indigo-400 border-indigo-500' : ''
      }`}
      style={{ left: position.x, top: position.y }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      onClick={(e) => {
        e.stopPropagation();
        selectNode(id);
      }}
    >
      {/* Input port (top center) */}
      <div
        data-port="input"
        className={`absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full border-2 border-white z-10 transition-colors ${
          connectingFrom && connectingFrom !== id
            ? 'bg-green-500 hover:bg-green-600 cursor-crosshair'
            : 'bg-gray-300 hover:bg-gray-400 cursor-pointer'
        }`}
        onClick={handleInputClick}
      />

      <Icon size={16} className="mx-auto mb-1 text-gray-500" />

      {isEditing ? (
        <input
          ref={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={handleLabelSubmit}
          onKeyDown={handleLabelKeyDown}
          className="w-full text-sm text-center bg-white border border-gray-300 rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-indigo-400"
          autoFocus
        />
      ) : (
        <p className="text-sm font-medium text-gray-800">{label}</p>
      )}

      <span className="text-[10px] text-gray-400 uppercase">{type}</span>

      {/* Output port (bottom center) */}
      <div
        data-port="output"
        className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-blue-500 rounded-full border-2 border-white cursor-pointer hover:bg-blue-600 z-10"
        onClick={handleOutputClick}
      />
    </div>
  );
}
