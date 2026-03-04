import { useState, useCallback, useRef } from 'react';
import { getAudioLevel } from '@/services/audio';
import { getPcmWorkletUrl } from '@/services/pcmWorklet';

const SILENCE_THRESHOLD = 0.02;
const SILENCE_TIMEOUT_MS = 8_000; // 8s silence → auto-stop (conversational)

interface UseVoiceRecordingOptions {
  /** Called for each PCM chunk (base64) as audio is captured */
  onAudioChunk?: (pcmBase64: string) => void;
  /** Called when recording auto-stops due to silence */
  onAutoStop?: () => void;
}

export function useVoiceRecording(options?: UseVoiceRecordingOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const recordingRef = useRef(false); // non-reactive flag for rAF closure

  const onAudioChunkRef = useRef(options?.onAudioChunk);
  onAudioChunkRef.current = options?.onAudioChunk;
  const onAutoStopRef = useRef(options?.onAutoStop);
  onAutoStopRef.current = options?.onAutoStop;

  const cleanup = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    analyserRef.current = null;
    silenceStartRef.current = null;
    recordingRef.current = false;
    setIsRecording(false);
    setAudioLevel(0);
  }, []);

  const startRecording = useCallback(async () => {
    // Create AudioContext in user-gesture scope to avoid suspension
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    streamRef.current = stream;

    if (audioContext.state !== 'running') {
      await audioContext.resume();
    }

    // Register the PCM capture worklet
    await audioContext.audioWorklet.addModule(getPcmWorkletUrl());

    const source = audioContext.createMediaStreamSource(stream);

    // Worklet node for PCM capture
    const workletNode = new AudioWorkletNode(audioContext, 'pcm-capture-processor');
    workletNodeRef.current = workletNode;

    workletNode.port.onmessage = (e: MessageEvent) => {
      if (e.data?.type === 'pcm') {
        // Worklet transfers raw Int16Array buffer; encode to base64 here
        // because btoa() is not available in AudioWorkletGlobalScope.
        const bytes = new Uint8Array(e.data.buffer as ArrayBuffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        onAudioChunkRef.current?.(btoa(binary));
      }
    };

    source.connect(workletNode);
    // Worklet doesn't need to connect to destination (no playback)

    // Analyser for audio level visualization + silence detection
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyserRef.current = analyser;

    // Silent gain so Web Audio processes the graph
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;
    analyser.connect(silentGain);
    silentGain.connect(audioContext.destination);

    silenceStartRef.current = null;
    recordingRef.current = true;
    setIsRecording(true);

    // Poll audio level for visualizer + silence detection
    const pollLevel = () => {
      if (!recordingRef.current) return;

      if (analyserRef.current) {
        const level = getAudioLevel(analyserRef.current);
        setAudioLevel(level);

        // Silence detection
        if (level < SILENCE_THRESHOLD) {
          silenceStartRef.current ??= Date.now();
          if (Date.now() - silenceStartRef.current >= SILENCE_TIMEOUT_MS) {
            cleanup();
            onAutoStopRef.current?.();
            return;
          }
        } else {
          silenceStartRef.current = null;
        }
      }

      animFrameRef.current = requestAnimationFrame(pollLevel);
    };
    pollLevel();
  }, [cleanup]);

  const stopRecording = useCallback(() => {
    cleanup();
  }, [cleanup]);

  return {
    isRecording,
    audioLevel,
    startRecording,
    stopRecording,
  };
}
