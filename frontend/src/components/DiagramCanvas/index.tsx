import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { MermaidRenderer } from './MermaidRenderer';
import { DiagramControls } from './DiagramControls';
import { ExportMenu } from './ExportMenu';
import { Canvas, ElementLibrary } from '@/components/ManualEditor';
import { useDiagramStore } from '@/stores/diagramStore';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';

export function DiagramCanvas() {
  const currentSyntax = useDiagramStore((s) => s.currentSyntax);
  const mode = useDiagramStore((s) => s.mode);

  const sessionId = useConversationStore((s) => s.sessionId);
  const addMessage = useConversationStore((s) => s.addMessage);
  const wsSend = useConversationStore((s) => s._wsSend);
  const setLoading = useUIStore((s) => s.setLoading);

  const handleAskToFix = (errorMessage: string) => {
    if (!wsSend) return;
    const fixRequest = `The diagram has a syntax error: "${errorMessage}". Please fix the Mermaid syntax and return a corrected diagram.`;

    addMessage({
      role: 'user',
      content: fixRequest,
      timestamp: new Date().toISOString(),
    });

    wsSend({
      action: 'message',
      sessionId,
      text: fixRequest,
      currentDiagram: currentSyntax || undefined,
    });

    setLoading(true);
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-gray-200 bg-white">
        <DiagramControls />
        <div className="pr-4">
          <ExportMenu />
        </div>
      </div>
      <div className="flex-1 overflow-hidden flex">
        {mode === 'manual' ? (
          <DndProvider backend={HTML5Backend}>
            <ElementLibrary />
            <div className="flex-1 relative">
              <Canvas />
            </div>
          </DndProvider>
        ) : (
          <div className="flex-1 overflow-auto p-4">
            <MermaidRenderer
              syntax={currentSyntax}
              onAskToFix={handleAskToFix}
            />
          </div>
        )}
      </div>
    </>
  );
}

export { MermaidRenderer } from './MermaidRenderer';
export { DiagramControls } from './DiagramControls';
export { ExportMenu } from './ExportMenu';
