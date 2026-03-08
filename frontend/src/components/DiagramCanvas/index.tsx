import { MermaidRenderer } from './MermaidRenderer';
import { useDiagramStore } from '@/stores/diagramStore';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';

export function DiagramCanvas() {
  const currentSyntax = useDiagramStore((s) => s.currentSyntax);
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
    <div className="w-full h-full overflow-hidden">
      <MermaidRenderer syntax={currentSyntax} onAskToFix={handleAskToFix} />
    </div>
  );
}

export { MermaidRenderer } from './MermaidRenderer';
export { DiagramControls } from './DiagramControls';
export { ExportMenu } from './ExportMenu';
