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
    <ul className="space-y-2 mt-3">
      {files.map((file) => (
        <li
          key={file.name}
          className="flex items-center justify-between text-sm p-2 bg-gray-50 rounded"
        >
          <span className="truncate">{file.name}</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{file.status}</span>
            {onRemove && (
              <button
                onClick={() => onRemove(file.name)}
                className="text-gray-400 hover:text-red-500"
              >
                &times;
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
