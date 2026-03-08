import { useState, useEffect, useCallback, useRef } from 'react';
import { TransformWrapper, TransformComponent, ReactZoomPanPinchRef } from 'react-zoom-pan-pinch';
import { LoadingSpinner } from '@/components/shared/LoadingSpinner';
import { useDiagramStore } from '@/stores/diagramStore';
import { useUIStore } from '@/stores/uiStore';
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
  const transformRef = useRef<ReactZoomPanPinchRef>(null);
  const setRenderedSvg = useDiagramStore((s) => s.setRenderedSvg);
  const theme = useUIStore((s) => s.theme);

  const renderDiagram = useCallback(async () => {
    if (!syntax) {
      setSvg('');
      setRenderError(null);
      setRenderedSvg('');
      return;
    }

    setIsRendering(true);
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const mermaid = (window as any).mermaid;
      if (!mermaid) throw new Error('Mermaid not loaded');
      mermaid.initialize({
        startOnLoad: false,
        theme: theme === 'dark' ? 'dark' : 'default',
      });

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
  }, [syntax, theme, onRenderComplete, onError, setRenderedSvg]);

  const fitToView = useCallback(() => {
    if (transformRef.current) {
      transformRef.current.centerView(1, 0);
    }
  }, []);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);

  // Re-fit diagram when SVG content changes
  useEffect(() => {
    if (svg) fitToView();
  }, [svg, fitToView]);

  if (isRendering) return <LoadingSpinner />;

  if (renderError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
        <div className="w-full max-w-lg glass rounded-xl p-4 border border-red-200 dark:border-red-500/20">
          <p className="text-sm font-medium text-red-600 dark:text-red-300 mb-1">Diagram syntax error</p>
          <p className="text-xs text-red-500 dark:text-red-400/80 font-mono break-all">{renderError}</p>
          {onAskToFix && (
            <button
              onClick={() => onAskToFix(renderError)}
              className="mt-3 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 dark:bg-red-500/15 dark:hover:bg-red-500/25 dark:text-red-300 dark:border-red-500/20 transition-colors"
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
      <div className="flex items-center justify-center h-full text-gray-300 dark:text-white/20">
        <p>Your diagram will appear here</p>
      </div>
    );
  }

  return (
    <TransformWrapper
      ref={transformRef}
      initialScale={1}
      minScale={0.1}
      maxScale={5}
      centerOnInit={true}
      onInit={fitToView}
      wheel={{ step: 0.1 }}
      doubleClick={{ mode: 'reset' }}
    >
      <TransformComponent
        wrapperStyle={{ width: '100%', height: '100%' }}
        contentStyle={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <div
          ref={containerRef}
          className="diagram-container p-8"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </TransformComponent>
    </TransformWrapper>
  );
}
