import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';

interface ConversationDisplayProps {
  onStopAudio?: () => void;
}

export function ConversationDisplay({ onStopAudio }: ConversationDisplayProps) {
  const { messages, currentTranscript, isAudioPlaying } = useConversationStore();
  const { isLoading, error } = useUIStore();

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 && !currentTranscript && (
        <div className="text-center text-gray-400 mt-8">
          <p className="text-lg font-medium">Start a conversation</p>
          <p className="text-sm mt-1">
            Describe the system you want to design
          </p>
        </div>
      )}

      {messages.map((msg, i) => (
        <div
          key={i}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-primary-500 text-white'
                : 'bg-gray-100 text-gray-900'
            }`}
          >
            {msg.agent && (
              <span className="text-xs opacity-70 block mb-1">{msg.agent}</span>
            )}
            {msg.content}
          </div>
        </div>
      ))}

      {currentTranscript && (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-primary-100 text-primary-700 italic">
            {currentTranscript}...
          </div>
        </div>
      )}

      {isAudioPlaying && (
        <div className="flex justify-start">
          <button
            onClick={onStopAudio}
            className="rounded-lg px-3 py-2 text-sm bg-blue-50 text-blue-600 flex items-center gap-2 hover:bg-blue-100 transition-colors cursor-pointer"
            title="Click to stop audio"
          >
            <span className="inline-flex gap-0.5">
              <span className="w-1 h-3 bg-blue-500 rounded-full animate-pulse" />
              <span className="w-1 h-4 bg-blue-500 rounded-full animate-pulse [animation-delay:150ms]" />
              <span className="w-1 h-2 bg-blue-500 rounded-full animate-pulse [animation-delay:300ms]" />
            </span>
            Speaking...
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="opacity-50"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}

      {isLoading && (
        <div className="flex justify-start">
          <div className="rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-500 animate-pulse">
            Thinking...
          </div>
        </div>
      )}

      {error && (
        <div className="flex justify-start">
          <div className="rounded-lg px-3 py-2 text-sm bg-red-50 text-red-600">
            {error}
          </div>
        </div>
      )}
    </div>
  );
}
