import { useState, useEffect, useCallback, useRef } from 'react';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useDiagramStore } from '@/stores/diagramStore';

interface MermaidRendererProps {
  syntax: string;
  onRenderComplete?: () => void;
  onError?: (error: Error) => void;
}

export function MermaidRenderer({
  syntax,
  onRenderComplete,
  onError,
}: MermaidRendererProps) {
  const [svg, setSvg] = useState<string>('');
  const [isRendering, setIsRendering] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const setRenderedSvg = useDiagramStore((s) => s.setRenderedSvg);

  const renderDiagram = useCallback(async () => {
    if (!syntax) {
      setSvg('');
      setRenderedSvg('');
      return;
    }

    setIsRendering(true);
    try {
      const mermaid = (await import('mermaid')).default;
      mermaid.initialize({ startOnLoad: false, theme: 'default' });

      const { svg: renderedSvg } = await mermaid.render('diagram', syntax);
      setSvg(renderedSvg);
      setRenderedSvg(renderedSvg);
      onRenderComplete?.();
    } catch (error) {
      setRenderedSvg('');
      onError?.(error as Error);
    } finally {
      setIsRendering(false);
    }
  }, [syntax, onRenderComplete, onError, setRenderedSvg]);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);

  if (isRendering) return <LoadingSpinner />;

  if (!svg) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <p>Your diagram will appear here</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="diagram-container w-full h-full flex items-center justify-center"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
