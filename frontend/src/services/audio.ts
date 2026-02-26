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

// ---- Audio Playback ----

let playbackContext: AudioContext | null = null;

function getPlaybackContext(sampleRate: number): AudioContext {
  if (!playbackContext || playbackContext.state === 'closed') {
    playbackContext = new AudioContext({ sampleRate });
  }
  // Resume if suspended (browser autoplay policy)
  if (playbackContext.state === 'suspended') {
    playbackContext.resume();
  }
  return playbackContext;
}

/**
 * Decode a base64 LPCM string to a Float32Array for Web Audio API.
 * Expects 16-bit signed little-endian PCM.
 */
function decodeLPCMBase64(base64: string): Float32Array {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  const dataView = new DataView(bytes.buffer);
  const sampleCount = bytes.length / 2; // 16-bit = 2 bytes per sample
  const float32 = new Float32Array(sampleCount);

  for (let i = 0; i < sampleCount; i++) {
    const int16 = dataView.getInt16(i * 2, true); // little-endian
    float32[i] = int16 / 32768; // normalize to [-1, 1]
  }

  return float32;
}

export interface AudioChunkPlayer {
  addChunk: (base64Audio: string) => void;
  finish: () => Promise<void>;
  stop: () => void;
  isPlaying: () => boolean;
}

/**
 * Create a chunked audio player that queues and plays LPCM audio chunks
 * as they arrive from the WebSocket, scheduling them gaplessly.
 */
export function createChunkPlayer(
  sampleRate: number = 24000,
  onStateChange?: (playing: boolean) => void,
): AudioChunkPlayer {
  const ctx = getPlaybackContext(sampleRate);
  let nextStartTime = 0;
  let playing = false;
  let stopped = false;
  let finishResolve: (() => void) | null = null;
  let pendingSources: AudioBufferSourceNode[] = [];

  const addChunk = (base64Audio: string) => {
    if (stopped) return;

    const samples = decodeLPCMBase64(base64Audio);
    const buffer = ctx.createBuffer(1, samples.length, sampleRate);
    buffer.getChannelData(0).set(samples);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    // Schedule right after the previous chunk for gapless playback
    const startTime = Math.max(ctx.currentTime, nextStartTime);
    source.start(startTime);
    nextStartTime = startTime + buffer.duration;

    if (!playing) {
      playing = true;
      onStateChange?.(true);
    }

    pendingSources.push(source);
    source.onended = () => {
      pendingSources = pendingSources.filter((s) => s !== source);
      if (pendingSources.length === 0 && finishResolve) {
        playing = false;
        onStateChange?.(false);
        finishResolve();
      }
    };
  };

  const finish = (): Promise<void> => {
    if (pendingSources.length === 0) {
      playing = false;
      onStateChange?.(false);
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      finishResolve = resolve;
    });
  };

  const stop = () => {
    stopped = true;
    pendingSources.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    });
    pendingSources = [];
    playing = false;
    onStateChange?.(false);
    if (finishResolve) finishResolve();
  };

  const isPlaying = () => playing;

  return { addChunk, finish, stop, isPlaying };
}
