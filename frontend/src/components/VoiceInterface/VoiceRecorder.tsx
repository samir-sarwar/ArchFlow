import { useCallback, useEffect, useRef, useState } from 'react';
import { useVoiceRecording } from '@/hooks/useVoiceRecording';
import { useConversation } from '@/hooks/useConversation';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';
import { AudioVisualizer } from './AudioVisualizer';

export function VoiceRecorder() {
  const {
    sendVoiceMessage,
    stopAudioPlayback,
    isConnected,
  } = useConversation();
  const { setRecording } = useConversationStore();
  const isAudioPlaying = useConversationStore((s) => s.isAudioPlaying);
  const voiceStatus = useConversationStore((s) => s.voiceStatus);
  const addNotification = useUIStore((s) => s.addNotification);
  // Ref keeps mimeType current for the handleAutoStop callback closure
  const mimeTypeRef = useRef('');

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
    isPaused,
    audioLevel,
    mimeType,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
  } = useVoiceRecording({
    onAutoStop: useCallback(async (audioBlob: Blob) => {
      addNotification('Recording stopped due to silence', 'info');
      setRecording(false);
      if (audioBlob.size > 0) {
        await sendVoiceMessage(audioBlob, mimeTypeRef.current || undefined);
      }
    }, [addNotification, setRecording, sendVoiceMessage]),
  });

  // Keep the ref in sync so handleAutoStop always has the latest mimeType
  mimeTypeRef.current = mimeType;

  const handleStart = async () => {
    // Barge-in: stop AI audio if playing
    if (isAudioPlaying) {
      stopAudioPlayback();
    }
    setShowReadyHint(false);
    setRecording(true);
    try {
      await startRecording();
    } catch {
      setRecording(false);
      addNotification('Microphone not available. Please check permissions.', 'error');
    }
  };

  const handleStop = async () => {
    setRecording(false);
    try {
      const audioBlob = await stopRecording();
      if (audioBlob.size > 0) {
        await sendVoiceMessage(audioBlob, mimeType);
      }
    } catch {
      addNotification('Failed to process recording. Please try again.', 'error');
    }
  };

  const handleTogglePause = () => {
    if (isPaused) {
      resumeRecording();
    } else {
      pauseRecording();
    }
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      await handleStop();
    } else {
      await handleStart();
    }
  };

  // Only disable when not connected — allow during loading/audio playback for barge-in
  const isDisabled = !isConnected;

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
        title={isRecording ? 'Stop recording' : 'Start voice input'}
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

      {/* Pause/Resume button — only shown while recording */}
      {isRecording && (
        <button
          type="button"
          onClick={handleTogglePause}
          className={`rounded-full p-2 transition-colors ${
            isPaused
              ? 'bg-yellow-100 hover:bg-yellow-200 text-yellow-700 ring-2 ring-yellow-300'
              : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
          }`}
          title={isPaused ? 'Resume recording' : 'Pause recording'}
        >
          {isPaused ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="currentColor"
              stroke="none"
            >
              <polygon points="6,4 20,12 6,20" />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="currentColor"
              stroke="none"
            >
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          )}
        </button>
      )}

      {isPaused && (
        <span className="text-xs text-yellow-600 font-medium">Paused</span>
      )}

      <AudioVisualizer isActive={isRecording && !isPaused} audioLevel={audioLevel} />

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
