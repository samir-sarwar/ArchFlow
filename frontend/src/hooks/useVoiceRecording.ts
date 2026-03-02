import { useState, useCallback, useRef } from 'react';
import { getAudioLevel } from '@/services/audio';

const SILENCE_THRESHOLD = 0.02; // Normalized 0-1; below this is "silence"
const SILENCE_TIMEOUT_MS = 60_000; // Auto-stop after 60s of silence

function getSupportedMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  return types.find((t) => MediaRecorder.isTypeSupported(t)) ?? '';
}

interface UseVoiceRecordingOptions {
  /** Called when recording auto-stops due to silence, with the captured audio blob */
  onAutoStop?: (audioBlob: Blob) => void;
}

export function useVoiceRecording(options?: UseVoiceRecordingOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const analyserStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animFrameRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const mimeTypeRef = useRef('');
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
        // Capture recorder ref before nulling so onstop closure can access it
        const recorder = mediaRecorderRef.current;
        // Null the ref immediately so pollLevel stops scheduling new frames
        mediaRecorderRef.current = null;

        recorder.onstop = () => {
          // Stop tracks AFTER recorder finishes — ensures final ondataavailable
          // chunk is flushed before the media track is torn down
          recorder.stream.getTracks().forEach((track) => track.stop());
          const blob = new Blob(chunksRef.current, {
            type: mimeTypeRef.current || 'audio/webm;codecs=opus',
          });
          chunksRef.current = [];
          resolve(blob);
        };

        // requestData() forces an immediate ondataavailable with any buffered
        // audio — critical for recordings shorter than the 500ms timeslice.
        // Wrapped in try-catch: Safari may not support requestData(), and a
        // throw here would reject the promise (stop() alone still works fine).
        try {
          if (recorder.state === 'recording') {
            recorder.requestData();
          }
        } catch { /* requestData not supported */ }
        recorder.stop();
      } else {
        resolve(new Blob([]));
      }

      // Stop cloned analyser stream tracks
      if (analyserStreamRef.current) {
        analyserStreamRef.current.getTracks().forEach((t) => t.stop());
        analyserStreamRef.current = null;
      }

      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
      analyserRef.current = null;
      silenceStartRef.current = null;
      setIsRecording(false);
      setIsPaused(false);
      setAudioLevel(0);
    });
  }, []);

  const startRecording = useCallback(async () => {
    // Create AudioContext synchronously while still inside the user-gesture
    // scope — creating it after an await can leave it suspended in Chrome/Safari
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Resume now that we have the stream; by this point the gesture chain is
    // established via getUserMedia so resume() is always permitted
    if (audioContext.state !== 'running') {
      await audioContext.resume();
    }

    const mimeType = getSupportedMimeType();
    mimeTypeRef.current = mimeType;
    const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

    // Clone stream for Web Audio analyser — Safari doesn't properly share
    // a single MediaStream between MediaRecorder and MediaStreamSource
    const analyserStream = stream.clone();
    analyserStreamRef.current = analyserStream;
    const source = audioContext.createMediaStreamSource(analyserStream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyserRef.current = analyser;

    // Connect analyser → silent gain → destination so the audio graph is processed
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;
    analyser.connect(silentGain);
    silentGain.connect(audioContext.destination);

    // Log recording errors so they surface in the console
    mediaRecorder.onerror = (event) => {
      console.error('[ArchFlow] MediaRecorder error:', event);
    };

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
    mimeType: mimeTypeRef.current,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
  };
}
