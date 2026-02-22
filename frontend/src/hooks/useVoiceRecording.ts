import { useState, useCallback, useRef } from 'react';

export function useVoiceRecording() {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const startRecording = useCallback(
    async (onAudioChunk: (chunk: Blob) => void) => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      // Audio level analysis
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      source.connect(analyser);
      analyserRef.current = analyser;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          onAudioChunk(event.data);
        }
      };

      mediaRecorder.start(500); // 500ms chunks
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
    },
    [],
  );

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream
        .getTracks()
        .forEach((track) => track.stop());
      mediaRecorderRef.current = null;
    }
    setIsRecording(false);
    setAudioLevel(0);
  }, []);

  return { isRecording, audioLevel, startRecording, stopRecording };
}
