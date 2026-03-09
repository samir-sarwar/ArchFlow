import { useState, useEffect, useCallback, useRef } from 'react';
import { TransformWrapper, TransformComponent, ReactZoomPanPinchRef, useControls } from 'react-zoom-pan-pinch';
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
  const wrapperRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<ReactZoomPanPinchRef>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const setRenderedSvg = useDiagramStore((s) => s.setRenderedSvg);
  const theme = useUIStore((s) => s.theme);

  // --- Eagerly configure Mermaid whenever the theme changes ---
  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mermaid = (window as any).mermaid;
    if (!mermaid) return;

    mermaid.initialize({
      startOnLoad: false,
      theme: theme === 'dark' ? 'base' : 'default',
      ...(theme === 'dark' && {
        themeVariables: {
          // Background & text
          background: '#0a0a1a',
          primaryTextColor: '#e2e8f0',
          secondaryTextColor: '#cbd5e1',
          tertiaryTextColor: '#94a3b8',

          // Lines / arrows — must be visible on dark bg
          lineColor: '#94a3b8',

          // Node fills
          primaryColor: '#1e293b',
          primaryBorderColor: '#475569',
          secondaryColor: '#1e1e2e',
          secondaryBorderColor: '#475569',
          tertiaryColor: '#1a1a2e',
          tertiaryBorderColor: '#475569',

          // Fonts
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',

          // Cluster / subgraph
          clusterBkg: '#111827',
          clusterBorder: '#374151',
          titleColor: '#e2e8f0',

          // Notes & labels
          noteBkgColor: '#1e293b',
          noteTextColor: '#e2e8f0',
          noteBorderColor: '#475569',
        },
      }),
    });
  }, [theme]);

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

      // Pre-validate with mermaid.parse() for clean error messages
      const validation = await validateMermaidSyntax(syntax);
      if (!validation.valid) {
        setRenderError(validation.error ?? 'Invalid Mermaid syntax');
        setRenderedSvg('');
        onError?.(new Error(validation.error));
        return;
      }

      const id = `diagram-${Date.now()}`;
      const { svg: renderedSvg } = await mermaid.render(id, syntax);
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
    if (!transformRef.current || !wrapperRef.current || !containerRef.current) return;

    const wrapperEl = wrapperRef.current;
    const contentEl = containerRef.current;

    // Use the actual rendered dimensions of the diagram container
    const contentW = contentEl.scrollWidth || contentEl.offsetWidth;
    const contentH = contentEl.scrollHeight || contentEl.offsetHeight;

    const wrapperW = wrapperEl.clientWidth;
    const wrapperH = wrapperEl.clientHeight;

    if (contentW === 0 || contentH === 0 || wrapperW === 0 || wrapperH === 0) return;

    // Fit with 85% padding so diagram doesn't touch edges
    const scale = Math.min(wrapperW / contentW, wrapperH / contentH) * 0.85;
    const clampedScale = Math.max(0.1, Math.min(scale, 2));

    // Calculate translate to center the scaled content in the wrapper
    const x = (wrapperW - contentW * clampedScale) / 2;
    const y = (wrapperH - contentH * clampedScale) / 2;

    transformRef.current.setTransform(x, y, clampedScale, 0);
  }, []);

  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);

  // Re-fit diagram when SVG content changes (small delay for DOM paint)
  useEffect(() => {
    if (svg) {
      const timer = setTimeout(() => {
        fitToView();
        // Fallback retry in case SVG dimensions weren't ready
        const retryTimer = setTimeout(() => fitToView(), 100);
        retryTimerRef.current = retryTimer;
      }, 50);
      return () => {
        clearTimeout(timer);
        if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      };
    }
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
    <div ref={wrapperRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <TransformWrapper
        ref={transformRef}
        initialScale={0.5}
        minScale={0.1}
        maxScale={5}
        centerOnInit={true}
        limitToBounds={false}
        wheel={{ step: 0.05, smoothStep: 0.01 }}
        pinch={{ step: 5 }}
        panning={{ velocityDisabled: false }}
        doubleClick={{ mode: 'reset' }}
      >
        <ZoomControls onFitToView={fitToView} />
        <TransformComponent
          wrapperStyle={{
            width: '100%',
            height: '100%',
            overflow: 'hidden',
          }}
          contentStyle={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            ref={containerRef}
            className="diagram-container"
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        </TransformComponent>
      </TransformWrapper>
    </div>
  );
}

/* ---------- Zoom Control Buttons ---------- */
function ZoomControls({ onFitToView }: { onFitToView: () => void }) {
  const { zoomIn, zoomOut } = useControls();

  return (
    <div className="absolute bottom-4 right-4 z-10 flex flex-col gap-1">
      <button
        onClick={() => zoomIn(0.3)}
        className="w-8 h-8 flex items-center justify-center rounded-lg glass text-gray-600 dark:text-white/70 hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-lg font-medium"
        title="Zoom in"
      >
        +
      </button>
      <button
        onClick={() => zoomOut(0.3)}
        className="w-8 h-8 flex items-center justify-center rounded-lg glass text-gray-600 dark:text-white/70 hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-lg font-medium"
        title="Zoom out"
      >
        −
      </button>
      <button
        onClick={() => onFitToView()}
        className="w-8 h-8 flex items-center justify-center rounded-lg glass text-gray-600 dark:text-white/70 hover:bg-black/5 dark:hover:bg-white/10 transition-colors"
        title="Fit to view"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
          <path fillRule="evenodd" d="M4.25 2A2.25 2.25 0 0 0 2 4.25v2.5a.75.75 0 0 0 1.5 0v-2.5a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 0 0-1.5h-2.5ZM13.25 2a.75.75 0 0 0 0 1.5h2.5a.75.75 0 0 1 .75.75v2.5a.75.75 0 0 0 1.5 0v-2.5A2.25 2.25 0 0 0 15.75 2h-2.5ZM3.5 13.25a.75.75 0 0 0-1.5 0v2.5A2.25 2.25 0 0 0 4.25 18h2.5a.75.75 0 0 0 0-1.5h-2.5a.75.75 0 0 1-.75-.75v-2.5ZM18 13.25a.75.75 0 0 0-1.5 0v2.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 0 0 1.5h2.5A2.25 2.25 0 0 0 18 15.75v-2.5Z" clipRule="evenodd" />
        </svg>
      </button>
    </div>
  );
}
