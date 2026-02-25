import type { CanvasConnection } from '@/types/diagram';

// Approximate node dimensions for centering connection endpoints
const NODE_HALF_W = 60;
const NODE_H = 70;

interface ConnectionLineProps {
  connection: CanvasConnection;
  sourcePos: { x: number; y: number };
  targetPos: { x: number; y: number };
  isSelected: boolean;
  onSelect: () => void;
}

export function ConnectionLine({
  connection,
  sourcePos,
  targetPos,
  isSelected,
  onSelect,
}: ConnectionLineProps) {
  // Source: bottom-center of node
  const x1 = sourcePos.x + NODE_HALF_W;
  const y1 = sourcePos.y + NODE_H;
  // Target: top-center of node
  const x2 = targetPos.x + NODE_HALF_W;
  const y2 = targetPos.y;

  // Bezier control points for a smooth curve
  const midY = (y1 + y2) / 2;
  const path = `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;

  return (
    <g
      className="pointer-events-auto cursor-pointer"
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
    >
      {/* Fat invisible stroke for easier click target */}
      <path d={path} stroke="transparent" strokeWidth={14} fill="none" />
      {/* Visible line */}
      <path
        d={path}
        stroke={isSelected ? '#6366f1' : '#9ca3af'}
        strokeWidth={isSelected ? 2.5 : 2}
        fill="none"
        markerEnd="url(#arrowhead)"
      />
      {/* Edge label */}
      {connection.label && (
        <text
          x={(x1 + x2) / 2}
          y={(y1 + y2) / 2 - 8}
          textAnchor="middle"
          className="text-xs"
          fill="#6b7280"
        >
          {connection.label}
        </text>
      )}
    </g>
  );
}
