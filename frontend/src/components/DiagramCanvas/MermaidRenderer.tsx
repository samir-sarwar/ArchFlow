import { useState, useEffect, useCallback, useRef } from 'react';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useDiagramStore } from '@/stores/diagramStore';
import { validateMermaidSyntax } from '@/utils/validateMermaid';

interface MermaidRendererProps {
  syntax: string;
  onRenderComplete?: () => void;
  onError?: (error: Error) => void;
  onAskToFix?: (errorMessage: string) => void;
}

export function MermaidRenderer({
  syntax,
  onRenderComplete,
  onError,
  onAskToFix,
}: MermaidRendererProps) {
  const [svg, setSvg] = useState<string>('');
  const [isRendering, setIsRendering] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const setRenderedSvg = useDiagramStore((s) => s.setRenderedSvg);

  const renderDiagram = useCallback(async () => {
    if (!syntax) {
      setSvg('');
      setRenderError(null);
      setRenderedSvg('');
      return;
    }

    setIsRendering(true);
    try {
      const mermaid = (await import('mermaid')).default;
      mermaid.initialize({ startOnLoad: false, theme: 'default' });

      // Pre-validate with mermaid.parse() for clean error messages
      const validation = await validateMermaidSyntax(syntax);
      if (!validation.valid) {
        setRenderError(validation.error ?? 'Invalid Mermaid syntax');
        setRenderedSvg('');
        onError?.(new Error(validation.error));
        return;
      }

      const { svg: renderedSvg } = await mermaid.render('diagram', syntax);
      setSvg(renderedSvg);
      setRenderError(null);
      setRenderedSvg(renderedSvg);
      onRenderComplete?.();
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Render failed';
      setRenderError(msg);
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

  if (renderError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
        <div className="w-full max-w-lg bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm font-medium text-red-800 mb-1">Diagram syntax error</p>
          <p className="text-xs text-red-700 font-mono break-all">{renderError}</p>
          {onAskToFix && (
            <button
              onClick={() => onAskToFix(renderError)}
              className="mt-3 px-3 py-1.5 text-xs font-medium rounded bg-red-100 hover:bg-red-200 text-red-800 border border-red-300"
            >
              Ask AI to fix
            </button>
          )}
        </div>
      </div>
    );
  }

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
