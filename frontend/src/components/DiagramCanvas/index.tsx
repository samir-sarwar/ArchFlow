import { MermaidRenderer } from './MermaidRenderer';
import { DiagramControls } from './DiagramControls';
import { ExportMenu } from './ExportMenu';
import { useDiagramStore } from '@/stores/diagramStore';

export function DiagramCanvas() {
  const { currentSyntax } = useDiagramStore();

  return (
    <>
      <div className="flex items-center justify-between border-b border-gray-200 bg-white">
        <DiagramControls />
        <div className="pr-4">
          <ExportMenu />
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <MermaidRenderer syntax={currentSyntax} />
      </div>
    </>
  );
}

export { MermaidRenderer } from './MermaidRenderer';
export { DiagramControls } from './DiagramControls';
export { ExportMenu } from './ExportMenu';
