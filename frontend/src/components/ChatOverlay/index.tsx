import { useState, useEffect, useRef } from 'react';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';
import { useConversation } from '@/hooks/useConversation';
import { X } from 'lucide-react';

export function ChatOverlay() {
  const [viewMode, setViewMode] = useState<'chat' | 'transcript'>('chat');
  const { messages, currentTranscript, isAudioPlaying } = useConversationStore();
  const { isLoading, error, chatOverlayOpen, toggleChatOverlay } = useUIStore();
  const { stopAudioPlayback } = useConversation();
  const scrollRef = useRef<HTMLDivElement>(null);

  const displayMessages =
    viewMode === 'transcript' ? messages.filter((m) => m.isVoice) : messages;

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayMessages.length, currentTranscript, isLoading]);

  if (!chatOverlayOpen) return null;

  const hasContent =
    displayMessages.length > 0 || currentTranscript || isLoading || error;

  if (!hasContent) return null;

  return (
    <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-20 w-full max-w-2xl px-4 animate-slide-up">
      <div className="glass-dark rounded-2xl overflow-hidden shadow-2xl shadow-gray-300/30 dark:shadow-black/30">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 dark:border-white/5">
          <div className="flex items-center gap-2">
            <div className="flex bg-gray-100 dark:bg-white/5 rounded-full p-0.5">
              <button
                onClick={() => setViewMode('chat')}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  viewMode === 'chat'
                    ? 'bg-primary-100 text-primary-700 dark:bg-primary-600/40 dark:text-primary-300 font-medium'
                    : 'text-gray-400 hover:text-gray-600 dark:text-white/40 dark:hover:text-white/60'
                }`}
              >
                Chat
              </button>
              <button
                onClick={() => setViewMode('transcript')}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  viewMode === 'transcript'
                    ? 'bg-primary-100 text-primary-700 dark:bg-primary-600/40 dark:text-primary-300 font-medium'
                    : 'text-gray-400 hover:text-gray-600 dark:text-white/40 dark:hover:text-white/60'
                }`}
              >
                Transcript
              </button>
            </div>
          </div>
          <button
            onClick={toggleChatOverlay}
            className="p-1 rounded-full text-gray-300 hover:text-gray-500 hover:bg-gray-100 dark:text-white/30 dark:hover:text-white/60 dark:hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="max-h-[45vh] overflow-y-auto p-4 space-y-3">
          {displayMessages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-primary-100 text-primary-900 border border-primary-200 dark:bg-primary-600/30 dark:text-primary-100 dark:border-primary-500/20'
                    : 'bg-gray-100 text-gray-700 border border-gray-200 dark:bg-white/5 dark:text-white/80 dark:border-white/5'
                }`}
              >
                {msg.agent && (
                  <span className="text-xs text-primary-500 dark:text-primary-400/60 block mb-1">
                    {msg.agent}
                  </span>
                )}
                <span className="whitespace-pre-wrap break-words">{msg.content}</span>
              </div>
            </div>
          ))}

          {currentTranscript && (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-xl px-3 py-2 text-sm bg-primary-50 text-primary-700 dark:bg-primary-600/15 dark:text-primary-200 italic border border-primary-100 dark:border-primary-500/10">
                {currentTranscript}...
              </div>
            </div>
          )}

          {isAudioPlaying && (
            <div className="flex justify-start">
              <button
                onClick={stopAudioPlayback}
                className="rounded-xl px-3 py-2 text-sm bg-primary-50 text-primary-600 dark:bg-primary-600/20 dark:text-primary-300 flex items-center gap-2 hover:bg-primary-100 dark:hover:bg-primary-600/30 transition-colors cursor-pointer border border-primary-200 dark:border-primary-500/15"
                title="Click to stop audio"
              >
                <span className="inline-flex gap-0.5">
                  <span className="w-1 h-3 bg-primary-500 dark:bg-primary-400 rounded-full animate-pulse" />
                  <span className="w-1 h-4 bg-primary-500 dark:bg-primary-400 rounded-full animate-pulse [animation-delay:150ms]" />
                  <span className="w-1 h-2 bg-primary-500 dark:bg-primary-400 rounded-full animate-pulse [animation-delay:300ms]" />
                </span>
                Speaking...
                <X className="w-3 h-3 opacity-50" />
              </button>
            </div>
          )}

          {isLoading && (
            <div className="flex justify-start">
              <div className="rounded-xl px-3 py-2 text-sm bg-gray-100 text-gray-400 dark:bg-white/5 dark:text-white/40 animate-pulse border border-gray-200 dark:border-white/5">
                Thinking...
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-start">
              <div className="rounded-xl px-3 py-2 text-sm bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300 border border-red-200 dark:border-red-500/20">
                {error}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
