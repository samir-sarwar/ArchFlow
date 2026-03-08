import { useCallback, useEffect, useRef, useState } from 'react';
import { useVoiceRecording } from '@/hooks/useVoiceRecording';
import { useConversation } from '@/hooks/useConversation';
import { useConversationStore } from '@/stores/conversationStore';
import { useUIStore } from '@/stores/uiStore';
import { AudioVisualizer } from '@/components/VoiceInterface/AudioVisualizer';
import { Square } from 'lucide-react';

export function VoiceIndicator() {
  const {
    startVoiceSession,
    sendAudioChunk,
    stopVoiceSession,
    stopAudioPlayback,
    isConnected,
  } = useConversation();
  const { setRecording } = useConversationStore();
  const isAudioPlaying = useConversationStore((s) => s.isAudioPlaying);
  const voiceStatus = useConversationStore((s) => s.voiceStatus);
  const isRecording = useConversationStore((s) => s.isRecording);
  const addNotification = useUIStore((s) => s.addNotification);

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
    isRecording: isActivelyRecording,
    audioLevel,
    startRecording,
    stopRecording,
  } = useVoiceRecording({
    onAudioChunk: useCallback(
      (pcmBase64: string) => {
        sendAudioChunk(pcmBase64);
      },
      [sendAudioChunk]
    ),
    onAutoStop: useCallback(() => {
      addNotification('Recording stopped due to silence', 'info');
      setRecording(false);
      stopVoiceSession();
    }, [addNotification, setRecording, stopVoiceSession]),
  });

  const handleStart = async () => {
    if (isAudioPlaying) stopAudioPlayback();
    setShowReadyHint(false);
    setRecording(true);
    try {
      startVoiceSession();
      await startRecording();
    } catch {
      setRecording(false);
      addNotification(
        'Microphone not available. Please check permissions.',
        'error'
      );
    }
  };

  const handleStop = () => {
    setRecording(false);
    stopRecording();
    stopVoiceSession();
  };

  const handleToggle = async () => {
    if (isActivelyRecording) {
      handleStop();
    } else {
      await handleStart();
    }
  };

  // Listen for toggle event from InputBar mic button
  useEffect(() => {
    const handler = () => {
      if (isConnected) handleToggle();
    };
    window.addEventListener('toggle-voice-recording', handler);
    return () => window.removeEventListener('toggle-voice-recording', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, isActivelyRecording]);

  // Only show when recording, has voice status, or ready hint
  const isVisible = isActivelyRecording || isRecording || voiceStatus || showReadyHint;
  if (!isVisible) return null;

  return (
    <div className="fixed bottom-[100px] left-1/2 -translate-x-1/2 z-30 animate-slide-up">
      <div className="glass rounded-2xl px-5 py-3 flex items-center gap-3 shadow-lg shadow-gray-300/30 dark:shadow-black/20">
        {isActivelyRecording && (
          <>
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <AudioVisualizer isActive audioLevel={audioLevel} />
            <button
              onClick={handleStop}
              className="p-1.5 rounded-full bg-red-100 text-red-500 hover:bg-red-200 dark:bg-red-500/20 dark:text-red-400 dark:hover:bg-red-500/30 transition-colors"
              title="Stop recording"
            >
              <Square className="w-3 h-3" fill="currentColor" />
            </button>
          </>
        )}

        {voiceStatus && !isActivelyRecording && (
          <span className="text-xs text-primary-600 dark:text-primary-300 font-medium animate-pulse">
            {voiceStatus.message}
          </span>
        )}

        {showReadyHint && !isActivelyRecording && !voiceStatus && (
          <button
            onClick={handleStart}
            className="text-xs text-primary-600 dark:text-primary-300 font-medium hover:text-primary-700 dark:hover:text-primary-200 transition-colors"
          >
            Tap to respond
          </button>
        )}
      </div>
    </div>
  );
}
