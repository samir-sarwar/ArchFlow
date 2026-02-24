import { useState, useCallback, useRef } from 'react';
import { getAudioLevel } from '@/services/audio';

export function useVoiceRecording() {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animFrameRef = useRef<number | null>(null);

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
    setIsRecording(true);

    // Poll audio level for visualizer
    const pollLevel = () => {
      if (analyserRef.current) {
        setAudioLevel(getAudioLevel(analyserRef.current));
      }
      if (mediaRecorderRef.current) {
        animFrameRef.current = requestAnimationFrame(pollLevel);
      }
    };
    pollLevel();
  }, []);

  const stopRecording = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      // Stop audio level polling
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

      setIsRecording(false);
      setAudioLevel(0);
    });
  }, []);

  return { isRecording, audioLevel, startRecording, stopRecording };
}
