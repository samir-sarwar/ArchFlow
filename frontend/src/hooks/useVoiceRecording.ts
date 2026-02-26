import { useState, useCallback, useRef } from 'react';
import { getAudioLevel } from '@/services/audio';

const SILENCE_THRESHOLD = 0.02; // Normalized 0-1; below this is "silence"
const SILENCE_TIMEOUT_MS = 60_000; // Auto-stop after 60s of silence

interface UseVoiceRecordingOptions {
  /** Called when recording auto-stops due to silence, with the captured audio blob */
  onAutoStop?: (audioBlob: Blob) => void;
}

export function useVoiceRecording(options?: UseVoiceRecordingOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animFrameRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const onAutoStopRef = useRef(options?.onAutoStop);
  onAutoStopRef.current = options?.onAutoStop;

  // Internal stop that resolves with blob — shared by manual stop and auto-stop
  const doStop = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }

      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.onstop = () => {
          const blob = new Blob(chunksRef.current, {
            type: 'audio/webm;codecs=opus',
          });
          chunksRef.current = [];
          resolve(blob);
        };

        mediaRecorderRef.current.stop();
        mediaRecorderRef.current.stream
          .getTracks()
          .forEach((track) => track.stop());
        mediaRecorderRef.current = null;
      } else {
        resolve(new Blob([]));
      }

      silenceStartRef.current = null;
      setIsRecording(false);
      setIsPaused(false);
      setAudioLevel(0);
    });
  }, []);

  const startRecording = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus',
    });

    // Audio level analysis
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyserRef.current = analyser;

    // Accumulate chunks
    chunksRef.current = [];
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    mediaRecorder.start(500); // 500ms chunks
    mediaRecorderRef.current = mediaRecorder;
    silenceStartRef.current = null;
    setIsRecording(true);
    setIsPaused(false);

    // Poll audio level for visualizer + silence detection
    const pollLevel = () => {
      if (analyserRef.current) {
        const level = getAudioLevel(analyserRef.current);
        setAudioLevel(level);

        // Silence detection (skip while paused)
        if (
          mediaRecorderRef.current &&
          mediaRecorderRef.current.state === 'recording'
        ) {
          if (level < SILENCE_THRESHOLD) {
            silenceStartRef.current ??= Date.now();
            if (Date.now() - silenceStartRef.current >= SILENCE_TIMEOUT_MS) {
              // Auto-stop: stop recording internally and notify parent with blob
              doStop().then((blob) => {
                onAutoStopRef.current?.(blob);
              });
              return;
            }
          } else {
            silenceStartRef.current = null;
          }
        }
      }
      if (mediaRecorderRef.current) {
        animFrameRef.current = requestAnimationFrame(pollLevel);
      }
    };
    pollLevel();
  }, [doStop]);

  const stopRecording = useCallback((): Promise<Blob> => {
    return doStop();
  }, [doStop]);

  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.pause();
      setIsPaused(true);
      silenceStartRef.current = null;
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
      setAudioLevel(0);
    }
  }, []);

  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'paused') {
      mediaRecorderRef.current.resume();
      setIsPaused(false);
      silenceStartRef.current = null;

      // Resume audio level polling with silence detection
      const pollLevel = () => {
        if (analyserRef.current) {
          const level = getAudioLevel(analyserRef.current);
          setAudioLevel(level);

          if (
            mediaRecorderRef.current &&
            mediaRecorderRef.current.state === 'recording'
          ) {
            if (level < SILENCE_THRESHOLD) {
              silenceStartRef.current ??= Date.now();
              if (Date.now() - silenceStartRef.current >= SILENCE_TIMEOUT_MS) {
                doStop().then((blob) => {
                  onAutoStopRef.current?.(blob);
                });
                return;
              }
            } else {
              silenceStartRef.current = null;
            }
          }
        }
        if (mediaRecorderRef.current) {
          animFrameRef.current = requestAnimationFrame(pollLevel);
        }
      };
      pollLevel();
    }
  }, [doStop]);

  return {
    isRecording,
    isPaused,
    audioLevel,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
  };
}
