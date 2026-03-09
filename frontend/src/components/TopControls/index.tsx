import { useState, useRef, useEffect } from 'react';
import { useDiagramStore } from '@/stores/diagramStore';
import { useUIStore } from '@/stores/uiStore';
import { downloadBlob, generateExportFilename } from '@/utils/downloadFile';
import {
  Undo2,
  Redo2,
  Download,
  Image,
  FileCode,
  Copy,
  Eye,
  Code2,
} from 'lucide-react';

export function TopControls() {
  const { undo, redo, historyIndex, history, currentSyntax, renderedSvg } =
    useDiagramStore();
  const activeView = useUIStore((s) => s.activeView);
  const setActiveView = useUIStore((s) => s.setActiveView);
  const [exportOpen, setExportOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!exportOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [exportOpen]);

  const handleExport = (format: 'png' | 'svg' | 'mermaid') => {
    setExportOpen(false);

    if (format === 'svg') {
      const blob = new Blob([renderedSvg], {
        type: 'image/svg+xml;charset=utf-8',
      });
      downloadBlob(blob, generateExportFilename('svg'));
      return;
    }

    if (format === 'mermaid') {
      const blob = new Blob([currentSyntax], {
        type: 'text/plain;charset=utf-8',
      });
      downloadBlob(blob, generateExportFilename('mmd'));
      return;
    }

    if (format === 'png') {
      const img = new window.Image();
      const svgBlob = new Blob([renderedSvg], {
        type: 'image/svg+xml;charset=utf-8',
      });
      const url = URL.createObjectURL(svgBlob);
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth * 2;
        canvas.height = img.naturalHeight * 2;
        const ctx = canvas.getContext('2d')!;
        ctx.scale(2, 2);
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, img.naturalWidth, img.naturalHeight);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        canvas.toBlob((pngBlob) => {
          if (pngBlob) downloadBlob(pngBlob, generateExportFilename('png'));
        }, 'image/png');
      };
      img.src = url;
    }
  };

  const handleCopyCode = async () => {
    setExportOpen(false);
    await navigator.clipboard.writeText(currentSyntax);
  };

  const btnClass =
    'p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-200/50 dark:text-white/50 dark:hover:text-white/80 dark:hover:bg-white/10 transition-colors disabled:opacity-30 disabled:hover:bg-transparent';

  return (
    <div className="fixed top-4 right-4 z-20 flex items-center gap-1 glass rounded-xl px-1 py-1 animate-fade-in">
      {/* Preview / Code toggle */}
      <div className="flex items-center bg-gray-100/50 dark:bg-white/5 rounded-lg p-0.5">
        <button
          onClick={() => setActiveView('preview')}
          className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
            activeView === 'preview'
              ? 'bg-white dark:bg-white/15 text-gray-900 dark:text-white shadow-sm'
              : 'text-gray-400 dark:text-white/40 hover:text-gray-600 dark:hover:text-white/60'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          Preview
        </button>
        <button
          onClick={() => setActiveView('code')}
          className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
            activeView === 'code'
              ? 'bg-white dark:bg-white/15 text-gray-900 dark:text-white shadow-sm'
              : 'text-gray-400 dark:text-white/40 hover:text-gray-600 dark:hover:text-white/60'
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          Code
        </button>
      </div>

      <div className="w-px h-5 bg-gray-200 dark:bg-white/10 mx-1" />

      <button
        onClick={undo}
        disabled={historyIndex <= 0}
        className={btnClass}
        title="Undo"
      >
        <Undo2 className="w-4 h-4" />
      </button>
      <button
        onClick={redo}
        disabled={historyIndex >= history.length - 1}
        className={btnClass}
        title="Redo"
      >
        <Redo2 className="w-4 h-4" />
      </button>

      <div className="w-px h-5 bg-gray-200 dark:bg-white/10 mx-1" />

      {/* Export dropdown */}
      <div ref={dropdownRef} className="relative">
        <button
          onClick={() => setExportOpen(!exportOpen)}
          className={`${btnClass} flex items-center gap-1.5`}
          title="Export"
        >
          <Download className="w-4 h-4" />
          <span className="text-xs">Export</span>
        </button>

        {exportOpen && (
          <div className="absolute top-full right-0 mt-2 glass-dark rounded-xl overflow-hidden min-w-[140px] shadow-xl shadow-gray-300/30 dark:shadow-black/30 animate-fade-in">
            <button
              onClick={() => handleExport('png')}
              disabled={!renderedSvg}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-white/60 dark:hover:text-white/90 dark:hover:bg-white/5 transition-colors disabled:opacity-30"
            >
              <Image className="w-3.5 h-3.5" />
              PNG
            </button>
            <button
              onClick={() => handleExport('svg')}
              disabled={!renderedSvg}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-white/60 dark:hover:text-white/90 dark:hover:bg-white/5 transition-colors disabled:opacity-30"
            >
              <FileCode className="w-3.5 h-3.5" />
              SVG
            </button>
            <button
              onClick={handleCopyCode}
              disabled={!currentSyntax}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-white/60 dark:hover:text-white/90 dark:hover:bg-white/5 transition-colors disabled:opacity-30"
            >
              <Copy className="w-3.5 h-3.5" />
              Copy Code
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
