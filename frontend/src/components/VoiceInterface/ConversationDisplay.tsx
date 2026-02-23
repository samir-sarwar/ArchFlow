import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';

export function ConversationDisplay() {
  const { messages, currentTranscript } = useConversationStore();
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
