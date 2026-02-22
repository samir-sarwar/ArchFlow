export async function requestMicrophoneAccess(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: 16000,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
}

export function createAudioAnalyser(stream: MediaStream): AnalyserNode {
  const audioContext = new AudioContext();
  const source = audioContext.createMediaStreamSource(stream);
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  return analyser;
}

export function getAudioLevel(analyser: AnalyserNode): number {
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  const sum = data.reduce((acc, val) => acc + val, 0);
  return sum / data.length / 255; // Normalized 0-1
}
