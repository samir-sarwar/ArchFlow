import { useConversationStore } from '@/stores/conversationStore';

export function VoiceRecorder() {
  const { isRecording, setRecording } = useConversationStore();

  const handleToggleRecording = () => {
    setRecording(!isRecording);
    // TODO: Implement microphone capture and WebSocket streaming
  };

  return (
    <div className="flex items-center gap-3 p-4">
      <button
        onClick={handleToggleRecording}
        className={`rounded-full p-4 transition-colors ${
          isRecording
            ? 'bg-red-500 hover:bg-red-600 text-white'
            : 'bg-primary-500 hover:bg-primary-600 text-white'
        }`}
      >
        {isRecording ? 'Stop' : 'Start Conversation'}
      </button>
    </div>
  );
}
