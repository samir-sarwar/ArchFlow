import { useState, useRef, useCallback, useEffect } from 'react';
import { useConversation } from '@/hooks/useConversation';
import { useUIStore } from '@/stores/uiStore';
import { useConversationStore } from '@/stores/conversationStore';
import { Mic, Plus, Send, MessageSquare } from 'lucide-react';

interface InputBarProps {
  uploadFile: (file: File) => void;
}

export function InputBar({ uploadFile }: InputBarProps) {
  const [input, setInput] = useState('');
  const [isMultiLine, setIsMultiLine] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { sendMessage, isConnected } = useConversation();
  const isLoading = useUIStore((s) => s.isLoading);
  const chatOverlayOpen = useUIStore((s) => s.chatOverlayOpen);
  const toggleChatOverlay = useUIStore((s) => s.toggleChatOverlay);
  const isRecording = useConversationStore((s) => s.isRecording);

  const resizeTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const scrollHeight = Math.min(ta.scrollHeight, 160); // max ~6 lines
    ta.style.height = `${scrollHeight}px`;
    setIsMultiLine(ta.scrollHeight > 36);
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [input, resizeTextarea]);

  const doSubmit = () => {
    if (!input.trim() || !isConnected || isLoading) return;
    sendMessage(input.trim());
    setInput('');
    setIsMultiLine(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    if (!chatOverlayOpen) {
      toggleChatOverlay();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSubmit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSubmit();
    }
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    selectedFiles.forEach(uploadFile);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-20 w-full max-w-2xl px-4">
      {/* Main input bar */}
      <form
        onSubmit={handleSubmit}
        className={`glass-input flex flex-col shadow-lg shadow-gray-300/30 dark:shadow-black/20 animate-slide-up transition-[border-radius] duration-200 ${isMultiLine ? 'rounded-2xl' : 'rounded-[24px]'
          }`}
      >
        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isConnected
              ? "Describe your architecture... e.g., 'Connect a new Data Lake to the Analytics Service'"
              : 'Connecting...'
          }
          disabled={!isConnected}
          rows={1}
          className="w-full bg-transparent text-gray-900 dark:text-white/90 text-sm placeholder:text-gray-400 dark:placeholder:text-white/30 focus:outline-none disabled:opacity-50 resize-none max-h-40 px-4 pt-3 pb-1 leading-5"
        />

        {/* Bottom action row */}
        <div className="flex items-center justify-between px-2 pb-2 pt-1">
          {/* Left group */}
          <div className="flex items-center gap-1">
            {/* Chat toggle */}
            <button
              type="button"
              onClick={toggleChatOverlay}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all whitespace-nowrap ${chatOverlayOpen
                  ? 'bg-primary-100 text-primary-600 border border-primary-200 dark:bg-primary-600/30 dark:text-primary-300 dark:border-primary-500/30'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-white/50 dark:hover:text-white/70 dark:hover:bg-white/5'
                }`}
              title="Toggle chat"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Chat</span>
            </button>

            {/* Attach button */}
            <button
              type="button"
              onClick={handleFileClick}
              disabled={!isConnected}
              className="p-2 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-white/40 dark:hover:text-white/70 dark:hover:bg-white/5 transition-colors disabled:opacity-30"
              title="Attach files"
            >
              <Plus className="w-4 h-4" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.png,.jpg,.jpeg"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          {/* Right group */}
          <div className="flex items-center gap-1">
            {/* Mic button */}
            <button
              type="button"
              disabled={!isConnected}
              className={`p-2 rounded-full transition-colors disabled:opacity-30 ${isRecording
                  ? 'text-red-500 bg-red-100 dark:text-red-400 dark:bg-red-500/20'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-white/40 dark:hover:text-white/70 dark:hover:bg-white/5'
                }`}
              title="Voice input"
              onClick={() => {
                window.dispatchEvent(new CustomEvent('toggle-voice-recording'));
              }}
            >
              <Mic className="w-4 h-4" />
            </button>

            {/* Send button */}
            <button
              type="submit"
              disabled={!input.trim() || !isConnected || isLoading}
              className="p-2 rounded-full bg-primary-600 text-white hover:bg-primary-500 disabled:opacity-30 disabled:hover:bg-primary-600 transition-colors"
              title="Send"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
