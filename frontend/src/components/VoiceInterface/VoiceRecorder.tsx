import { useCallback, useEffect, useRef, useState } from 'react';
import { useVoiceRecording } from '@/hooks/useVoiceRecording';
import { useConversation } from '@/hooks/useConversation';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';
import { AudioVisualizer } from './AudioVisualizer';

export function VoiceRecorder() {
  const {
    startVoiceSession,
    sendAudioChunk,
    stopVoiceSession,
    stopAudioPlayback,
    isConnected,
    isVoiceServerAvailable,
  } = useConversation();
  const { setRecording } = useConversationStore();
  const isAudioPlaying = useConversationStore((s) => s.isAudioPlaying);
  const voiceStatus = useConversationStore((s) => s.voiceStatus);
  const addNotification = useUIStore((s) => s.addNotification);

  // "Ready to listen" hint after AI finishes speaking
  const [showReadyHint, setShowReadyHint] = useState(false);
  const prevAudioPlayingRef = useRef(false);
  useEffect(() => {
    if (prevAudioPlayingRef.current && !isAudioPlaying) {
      setShowReadyHint(true);
      const timer = setTimeout(() => setShowReadyHint(false), 3000);
      return () => clearTimeout(timer);
    }
    prevAudioPlayingRef.current = isAudioPlaying;
  }, [isAudioPlaying]);

  const {
    isRecording,
    audioLevel,
    startRecording,
    stopRecording,
  } = useVoiceRecording({
    onAudioChunk: useCallback((pcmBase64: string) => {
      sendAudioChunk(pcmBase64);
    }, [sendAudioChunk]),
    onAutoStop: useCallback(() => {
      addNotification('Recording stopped due to silence', 'info');
      setRecording(false);
      stopVoiceSession();
    }, [addNotification, setRecording, stopVoiceSession]),
  });

  const handleStart = async () => {
    // Barge-in: stop AI audio if playing
    if (isAudioPlaying) {
      stopAudioPlayback();
    }
    setShowReadyHint(false);
    setRecording(true);
    try {
      startVoiceSession();
      await startRecording();
    } catch {
      setRecording(false);
      addNotification('Microphone not available. Please check permissions.', 'error');
    }
  };

  const handleStop = () => {
    setRecording(false);
    stopRecording();
    stopVoiceSession();
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      handleStop();
    } else {
      await handleStart();
    }
  };

  // Only disable when not connected or no separate voice server is deployed
  const isDisabled = !isConnected || !isVoiceServerAvailable;

  return (
    <div className="flex items-center gap-2">
      {/* Main mic button — start or stop recording */}
      <button
        type="button"
        onClick={handleToggleRecording}
        disabled={isDisabled}
        className={`rounded-full p-2 transition-colors disabled:opacity-50 ${
          isRecording
            ? 'bg-red-500 hover:bg-red-600 text-white'
            : showReadyHint
              ? 'bg-blue-100 hover:bg-blue-200 text-blue-700 ring-2 ring-blue-400 animate-pulse'
              : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
        }`}
        title={isRecording ? 'Stop recording' : isVoiceServerAvailable ? 'Start voice input' : 'Voice unavailable (no voice server configured)'}
      >
        {isRecording ? (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="currentColor"
            stroke="none"
          >
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
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
        )}
      </button>

      <AudioVisualizer isActive={isRecording} audioLevel={audioLevel} />

      {voiceStatus && !isRecording && (
        <span className="text-xs text-blue-600 font-medium animate-pulse">
          {voiceStatus.message}
        </span>
      )}

      {showReadyHint && !isRecording && !voiceStatus && (
        <span className="text-xs text-blue-600 font-medium">
          Tap to respond
        </span>
      )}
    </div>
  );
}
