import { useDiagramStore } from '@/stores/diagramStore';
import { downloadBlob, generateExportFilename } from '@/utils/downloadFile';

export function ExportMenu() {
  const { currentSyntax, renderedSvg } = useDiagramStore();

  const handleExport = (format: 'png' | 'svg' | 'mermaid') => {
    if (format === 'svg') {
      const blob = new Blob([renderedSvg], { type: 'image/svg+xml;charset=utf-8' });
      downloadBlob(blob, generateExportFilename('svg'));
      return;
    }

    if (format === 'mermaid') {
      const blob = new Blob([currentSyntax], { type: 'text/plain;charset=utf-8' });
      downloadBlob(blob, generateExportFilename('mmd'));
      return;
    }

    if (format === 'png') {
      const img = new Image();
      const svgBlob = new Blob([renderedSvg], { type: 'image/svg+xml;charset=utf-8' });
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
    await navigator.clipboard.writeText(currentSyntax);
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => handleExport('png')}
        disabled={!renderedSvg}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
      >
        PNG
      </button>
      <button
        onClick={() => handleExport('svg')}
        disabled={!renderedSvg}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
      >
        SVG
      </button>
      <button
        onClick={handleCopyCode}
        disabled={!currentSyntax}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
      >
        Copy Code
      </button>
    </div>
  );
}
