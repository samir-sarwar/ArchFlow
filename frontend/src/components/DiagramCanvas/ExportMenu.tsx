import { useDiagramStore } from '@/stores/diagramStore';

export function ExportMenu() {
  const { currentSyntax } = useDiagramStore();

  const handleExport = (_format: 'png' | 'svg' | 'mermaid') => {
    // TODO: Implement export functionality
  };

  const handleCopyCode = async () => {
    await navigator.clipboard.writeText(currentSyntax);
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => handleExport('png')}
        disabled={!currentSyntax}
        className="px-3 py-1 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
      >
        PNG
      </button>
      <button
        onClick={() => handleExport('svg')}
        disabled={!currentSyntax}
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
