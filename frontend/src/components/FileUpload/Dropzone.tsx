export function Dropzone() {
  // TODO: Implement drag-and-drop file upload with react-dropzone
  return (
    <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-primary-400 transition-colors">
      <p className="text-sm text-gray-500">
        Drop files here or click to browse
      </p>
      <p className="text-xs text-gray-400 mt-1">
        PDF, DOCX, TXT, PNG, JPG (max 10MB)
      </p>
    </div>
  );
}
