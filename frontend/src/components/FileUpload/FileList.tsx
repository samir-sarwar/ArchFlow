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

export function FileList({ files, onRemove }: FileListProps) {
  if (files.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {files.map((file) => (
        <div
          key={file.name}
          className="flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200 dark:bg-white/5 dark:text-white/60 dark:border-white/5"
        >
          <span className="truncate max-w-[120px]">{file.name}</span>
          <span className="text-gray-300 dark:text-white/25">{file.status}</span>
          {onRemove && (
            <button
              onClick={() => onRemove(file.name)}
              className="text-gray-300 hover:text-red-500 dark:text-white/30 dark:hover:text-red-400 transition-colors"
            >
              &times;
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
