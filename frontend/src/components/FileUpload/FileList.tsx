import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface UploadedFile {
  name: string;
  size: number;
  type: string;
  status: 'uploading' | 'processing' | 'ready' | 'error';
}

interface FileListProps {
  files: UploadedFile[];
  onRemove?: (fileName: string) => void;
}

const statusConfig: Record<
  UploadedFile['status'],
  { label: string; className: string }
> = {
  uploading: {
    label: 'Uploading…',
    className: 'text-gray-400 dark:text-white/40',
  },
  processing: {
    label: 'Processing…',
    className: 'text-amber-500 dark:text-amber-400',
  },
  ready: {
    label: 'Ready',
    className: 'text-emerald-500 dark:text-emerald-400',
  },
  error: {
    label: 'Error',
    className: 'text-red-500 dark:text-red-400',
  },
};

export function FileList({ files, onRemove }: FileListProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (files.length === 0) return null;

  return (
    <div className="fixed top-[68px] right-4 z-20 animate-fade-in flex flex-col items-end gap-2">
      {/* Toggle button */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-white/50 hover:text-gray-700 dark:hover:text-white/70 glass rounded-lg transition-colors"
        title={collapsed ? 'Show files' : 'Hide files'}
      >
        <span>Files ({files.length})</span>
        {collapsed ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronUp className="w-3.5 h-3.5" />
        )}
      </button>

      {/* File pills */}
      {!collapsed && (
        <div className="flex flex-col gap-1.5">
          {files.map((file) => {
            const status = statusConfig[file.status];
            return (
              <div
                key={file.name}
                className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg glass min-w-[180px] max-w-[220px]"
              >
                <span className="truncate flex-1 text-gray-700 dark:text-white/70">
                  {file.name}
                </span>
                <span className={`whitespace-nowrap font-medium ${status.className}`}>
                  {status.label}
                </span>
                {onRemove && (
                  <button
                    onClick={() => onRemove(file.name)}
                    className="text-gray-300 hover:text-red-500 dark:text-white/30 dark:hover:text-red-400 transition-colors ml-0.5"
                  >
                    &times;
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
