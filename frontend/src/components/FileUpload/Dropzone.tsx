import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
  overlay?: boolean;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
};

const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export function Dropzone({ onFilesSelected, disabled, overlay }: DropzoneProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFilesSelected(acceptedFiles);
      }
    },
    [onFilesSelected]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: ACCEPTED_TYPES,
      maxSize: MAX_SIZE,
      disabled,
      multiple: true,
      noClick: overlay,
      noKeyboard: overlay,
    });

  if (overlay) {
    return (
      <div
        {...getRootProps()}
        className={`w-full h-full transition-colors ${
          isDragActive ? 'bg-primary-100/50 dark:bg-primary-600/10' : ''
        }`}
      >
        <input {...getInputProps()} />
        {isDragActive && (
          <div className="absolute inset-0 flex items-center justify-center z-40 pointer-events-none">
            <div className="glass rounded-2xl px-8 py-6 text-center shadow-2xl shadow-gray-300/30 dark:shadow-black/30 animate-fade-in">
              <p className="text-sm text-primary-600 dark:text-primary-300 font-medium">
                Drop files here...
              </p>
              <p className="text-xs text-gray-400 dark:text-white/30 mt-1">
                PDF, TXT, PNG, JPG (max 10MB)
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-primary-400 bg-primary-50 dark:bg-primary-600/10'
            : 'border-gray-300 hover:border-primary-300 dark:border-white/10 dark:hover:border-primary-400/50'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-sm text-primary-600 dark:text-primary-300">Drop files here...</p>
        ) : (
          <>
            <p className="text-sm text-gray-500 dark:text-white/40">
              Drop files here or click to browse
            </p>
            <p className="text-xs text-gray-400 dark:text-white/20 mt-1">
              PDF, TXT, PNG, JPG (max 10MB)
            </p>
          </>
        )}
      </div>
      {fileRejections.length > 0 && (
        <p className="text-xs text-red-500 dark:text-red-400 mt-1">
          {fileRejections[0].errors[0]?.message || 'File rejected'}
        </p>
      )}
    </div>
  );
}
