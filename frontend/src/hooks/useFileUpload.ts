import { useState, useCallback } from 'react';

interface UploadedFile {
  name: string;
  size: number;
  type: string;
  status: 'uploading' | 'processing' | 'ready' | 'error';
}

export function useFileUpload() {
  const [files, setFiles] = useState<UploadedFile[]>([]);

  const uploadFile = useCallback(async (_file: File) => {
    // TODO: Get presigned URL from backend, upload to S3
  }, []);

  const removeFile = useCallback((fileName: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== fileName));
  }, []);

  return { files, uploadFile, removeFile };
}
