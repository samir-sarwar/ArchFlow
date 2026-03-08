import { useCallback, useState, useEffect, useRef } from 'react';
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

/**
 * Detects when files are being dragged over the document (from the OS).
 * Returns true while an external drag is in progress so we can enable
 * pointer-events on the dropzone overlay only when needed.
 */
function useDocumentDrag() {
  const [isDraggingOverDocument, setIsDraggingOverDocument] = useState(false);
  const counterRef = useRef(0);

  useEffect(() => {
    const onDragEnter = (e: DragEvent) => {
      // Only react to file drags, not in-page drags
      if (e.dataTransfer?.types?.includes('Files')) {
        counterRef.current++;
        if (counterRef.current === 1) setIsDraggingOverDocument(true);
      }
    };
    const onDragLeave = () => {
      counterRef.current = Math.max(0, counterRef.current - 1);
      if (counterRef.current === 0) setIsDraggingOverDocument(false);
    };
    const onDrop = () => {
      counterRef.current = 0;
      setIsDraggingOverDocument(false);
    };
    const onDragEnd = () => {
      counterRef.current = 0;
      setIsDraggingOverDocument(false);
    };

    document.addEventListener('dragenter', onDragEnter);
    document.addEventListener('dragleave', onDragLeave);
    document.addEventListener('drop', onDrop);
    document.addEventListener('dragend', onDragEnd);
    return () => {
      document.removeEventListener('dragenter', onDragEnter);
      document.removeEventListener('dragleave', onDragLeave);
      document.removeEventListener('drop', onDrop);
      document.removeEventListener('dragend', onDragEnd);
    };
  }, []);

  return isDraggingOverDocument;
}

export function Dropzone({ onFilesSelected, disabled, overlay }: DropzoneProps) {
  const isDraggingOverDocument = useDocumentDrag();

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
    // The overlay is pointer-events-none by default so all mouse / touch
    // events pass through to the diagram canvas (zoom, pan, pinch).
    // When an external file drag is detected at the document level we
    // flip to pointer-events-auto so react-dropzone can handle the drop.
    const active = isDraggingOverDocument || isDragActive;

    return (
      <div
        {...getRootProps()}
        className={`fixed inset-0 z-30 transition-colors ${active
            ? 'pointer-events-auto bg-primary-100/50 dark:bg-primary-600/10'
            : 'pointer-events-none'
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
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${isDragActive
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
