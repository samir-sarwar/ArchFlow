import { useState } from 'react';
import { ConversationDisplay } from './ConversationDisplay';
import { VoiceRecorder } from './VoiceRecorder';
import { Dropzone, FileList } from '@/components/FileUpload';
import { useConversation } from '@/hooks/useConversation';
import { useFileUpload } from '@/hooks/useFileUpload';
import { useUIStore } from '@/stores/uiStore';

export function VoiceInterface() {
  const [input, setInput] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const [viewMode, setViewMode] = useState<'chat' | 'transcript'>('chat');
  const { sendMessage, sendWsMessage, stopAudioPlayback, isConnected } = useConversation();
  const { files, uploadFile, removeFile } = useFileUpload(sendWsMessage);
  const isLoading = useUIStore((s) => s.isLoading);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !isConnected || isLoading) return;
    sendMessage(input.trim());
    setInput('');
  };

  const handleFilesSelected = (selectedFiles: File[]) => {
    selectedFiles.forEach(uploadFile);
  };

  return (
    <>
      <div className="flex justify-center pt-4 border-b border-gray-100 bg-white z-10 sticky top-0">
        <div className="bg-gray-100 p-1 flex rounded-lg">
          <button
            onClick={() => setViewMode('chat')}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${viewMode === 'chat' ? 'bg-white shadow-sm font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            Chat
          </button>
          <button
            onClick={() => setViewMode('transcript')}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${viewMode === 'transcript' ? 'bg-white shadow-sm font-medium text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            Transcript
          </button>
        </div>
      </div>
      <ConversationDisplay onStopAudio={stopAudioPlayback} viewMode={viewMode} />

      {/* File upload section */}
      <div className="px-4 py-2 border-t border-gray-100">
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
        >
          {showUpload ? 'Hide upload' : 'Attach files'}
        </button>
        {showUpload && (
          <div className="mt-2">
            <Dropzone
              onFilesSelected={handleFilesSelected}
              disabled={!isConnected}
            />
          </div>
        )}
        {files.length > 0 && <FileList files={files} onRemove={removeFile} />}
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 p-4 border-t border-gray-200"
      >
        <VoiceRecorder />
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isConnected ? 'Describe your architecture...' : 'Connecting...'}
          disabled={!isConnected}
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || !isConnected || isLoading}
          className="rounded-lg bg-primary-500 px-4 py-2 text-sm text-white hover:bg-primary-600 disabled:opacity-50 transition-colors"
        >
          {isLoading ? 'Thinking...' : 'Send'}
        </button>
      </form>
    </>
  );
}

export { VoiceRecorder } from './VoiceRecorder';
export { ConversationDisplay } from './ConversationDisplay';
export { AudioVisualizer } from './AudioVisualizer';
