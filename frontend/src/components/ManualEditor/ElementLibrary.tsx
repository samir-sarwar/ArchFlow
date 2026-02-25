import { useDrag } from 'react-dnd';
import { DND_ITEM_TYPES } from '@/types/diagram';
import type { NodeType, DraggedLibraryItem } from '@/types/diagram';
import { Server, Database, Globe, HardDrive, type LucideIcon } from 'lucide-react';

const ELEMENT_TEMPLATES: {
  type: NodeType;
  label: string;
  icon: LucideIcon;
}[] = [
  { type: 'service', label: 'Service', icon: Server },
  { type: 'database', label: 'Database', icon: Database },
  { type: 'loadbalancer', label: 'Load Balancer', icon: Globe },
  { type: 'cache', label: 'Cache', icon: HardDrive },
];

function DraggableElement({
  type,
  label,
  icon: Icon,
}: (typeof ELEMENT_TEMPLATES)[number]) {
  const [{ isDragging }, dragRef] = useDrag(() => ({
    type: DND_ITEM_TYPES.LIBRARY_ELEMENT,
    item: { type, label } satisfies DraggedLibraryItem,
    collect: (monitor) => ({ isDragging: monitor.isDragging() }),
  }));

  return (
    <div
      ref={dragRef}
      className={`flex items-center gap-2 p-2 rounded border border-gray-200 bg-white cursor-grab hover:border-gray-400 hover:shadow-sm transition-all ${
        isDragging ? 'opacity-50' : ''
      }`}
    >
      <Icon size={16} className="text-gray-500" />
      <span className="text-sm text-gray-700">{label}</span>
    </div>
  );
}

export function ElementLibrary() {
  return (
    <div className="w-48 border-r border-gray-200 p-3 bg-white flex flex-col gap-2 shrink-0">
      <h3 className="text-sm font-medium text-gray-700 mb-1">Elements</h3>
      <p className="text-xs text-gray-400 mb-2">Drag onto canvas</p>
      {ELEMENT_TEMPLATES.map((tmpl) => (
        <DraggableElement key={tmpl.type} {...tmpl} />
      ))}
    </div>
  );
}
