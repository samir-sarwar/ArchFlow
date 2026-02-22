interface NodeComponentProps {
  id: string;
  label: string;
  type: 'service' | 'database' | 'loadbalancer' | 'cache' | 'custom';
  position: { x: number; y: number };
  isSelected?: boolean;
}

export function NodeComponent({ label, type, isSelected }: NodeComponentProps) {
  // TODO: Implement draggable, resizable node
  return (
    <div
      className={`p-2 rounded border text-sm ${
        isSelected ? 'border-primary-500 ring-2 ring-primary-200' : 'border-gray-300'
      }`}
    >
      <span className="text-xs text-gray-500">{type}</span>
      <p>{label}</p>
    </div>
  );
}
