import { useVoiceRecording } from '@/hooks/useVoiceRecording';
import { useConversation } from '@/hooks/useConversation';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';
import { AudioVisualizer } from './AudioVisualizer';

export function VoiceRecorder() {
  const { isRecording, audioLevel, startRecording, stopRecording } =
    useVoiceRecording();
  const { sendVoiceMessage, isConnected } = useConversation();
  const { setRecording } = useConversationStore();
  const isLoading = useUIStore((s) => s.isLoading);

  const handleToggleRecording = async () => {
    if (isRecording) {
      setRecording(false);
      const audioBlob = await stopRecording();
      if (audioBlob.size > 0) {
        await sendVoiceMessage(audioBlob);
      }
    } else {
      setRecording(true);
      await startRecording();
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleToggleRecording}
        disabled={!isConnected || isLoading}
        className={`rounded-full p-2 transition-colors disabled:opacity-50 ${
          isRecording
            ? 'bg-red-500 hover:bg-red-600 text-white'
            : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
        }`}
        title={isRecording ? 'Stop recording' : 'Start voice input'}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" x2="12" y1="19" y2="22" />
        </svg>
      </button>
      <AudioVisualizer isActive={isRecording} audioLevel={audioLevel} />
    </div>
  );
}
