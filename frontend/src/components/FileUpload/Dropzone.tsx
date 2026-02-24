import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
};

const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export function Dropzone({ onFilesSelected, disabled }: DropzoneProps) {
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
    });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p className="text-sm text-blue-600">Drop files here...</p>
        ) : (
          <>
            <p className="text-sm text-gray-500">
              Drop files here or click to browse
            </p>
            <p className="text-xs text-gray-400 mt-1">
              PDF, TXT, PNG, JPG (max 10MB)
            </p>
          </>
        )}
      </div>
      {fileRejections.length > 0 && (
        <p className="text-xs text-red-500 mt-1">
          {fileRejections[0].errors[0]?.message || 'File rejected'}
        </p>
      )}
    </div>
  );
}
