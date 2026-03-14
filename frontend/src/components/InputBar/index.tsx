import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { useConversation } from '@/hooks/useConversation';
import { useUIStore } from '@/stores/uiStore';
import { useConversationStore } from '@/stores/conversationStore';
import { Mic, Plus, Send, MessageSquare, Github } from 'lucide-react';

// Matches @github: followed by a URL (or partial text) anywhere in the input
const GITHUB_MENTION_RE = /@github:\s*\S*/i;

interface InputBarProps {
  uploadFile: (file: File) => void;
}

export function InputBar({ uploadFile }: InputBarProps) {
  const [input, setInput] = useState('');
  const [isMultiLine, setIsMultiLine] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const githubMatch = useMemo(() => GITHUB_MENTION_RE.exec(input), [input]);
  const hasGithubMention = !!githubMatch;
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

  // Sync highlight overlay scroll with textarea
  const syncScroll = useCallback(() => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

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
        {/* Text input with @github: highlight overlay */}
        <div className="relative w-full">
          {/* Highlight overlay — renders colored @github: mention behind the transparent textarea */}
          {hasGithubMention && (
            <div
              ref={highlightRef}
              aria-hidden
              className="absolute inset-0 pointer-events-none px-4 pt-3 pb-1 text-sm leading-5 whitespace-pre-wrap break-words overflow-hidden"
            >
              <span className="text-gray-900 dark:text-white/90">
                {input.slice(0, githubMatch!.index)}
              </span>
              <span className="text-purple-500 dark:text-purple-400">
                {githubMatch![0]}
              </span>
              <span className="text-gray-900 dark:text-white/90">
                {input.slice(githubMatch!.index + githubMatch![0].length)}
              </span>
            </div>
          )}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onScroll={syncScroll}
            placeholder={
              isConnected
                ? "Describe your architecture... or '@github: <repo-url>' to add repo context"
                : 'Connecting...'
            }
            disabled={!isConnected}
            rows={1}
            className={`w-full bg-transparent text-sm placeholder:text-gray-400 dark:placeholder:text-white/30 focus:outline-none disabled:opacity-50 resize-none max-h-40 px-4 pt-3 pb-1 leading-5 ${hasGithubMention
                ? 'text-transparent caret-gray-900 dark:caret-white'
                : 'text-gray-900 dark:text-white/90'
              }`}
          />
          {/* GitHub indicator icon */}
          {hasGithubMention && (
            <div className="absolute right-3 top-3 text-purple-500 dark:text-purple-400">
              <Github className="w-4 h-4" />
            </div>
          )}
        </div>

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
