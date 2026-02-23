import { useState } from 'react';
import { ConversationDisplay } from './ConversationDisplay';
import { useConversation } from '@/hooks/useConversation';
import { useUIStore } from '@/stores/uiStore';

export function VoiceInterface() {
  const [input, setInput] = useState('');
  const { sendMessage, isConnected } = useConversation();
  const isLoading = useUIStore((s) => s.isLoading);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !isConnected || isLoading) return;
    sendMessage(input.trim());
    setInput('');
  };

  return (
    <>
      <ConversationDisplay />
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 p-4 border-t border-gray-200"
      >
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

export { ConversationDisplay } from './ConversationDisplay';
export { AudioVisualizer } from './AudioVisualizer';
