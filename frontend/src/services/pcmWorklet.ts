/**
 * PCM Capture AudioWorklet — inlined as a Blob URL.
 *
 * Downsamples from the AudioContext's native sample rate (typically 48kHz)
 * to 16kHz mono Int16 PCM, then transfers the raw Int16Array buffer to the
 * main thread every ~100ms. Base64 encoding happens on the main thread
 * because btoa() is not available in AudioWorkletGlobalScope.
 */

const WORKLET_SOURCE = /* js */ `
const TARGET_RATE = 16000;
const CHUNK_DURATION_MS = 100;

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._samplesNeeded = Math.floor(TARGET_RATE * CHUNK_DURATION_MS / 1000);
    // Track fractional position for accurate resampling across frames
    this._srcPosition = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];
    const step = sampleRate / TARGET_RATE;

    // Downsample: step through source samples at the ratio
    while (this._srcPosition < channelData.length) {
      const idx = Math.floor(this._srcPosition);
      const s = Math.max(-1, Math.min(1, channelData[idx]));
      this._buffer.push(s);
      this._srcPosition += step;
    }
    // Carry over fractional position to next frame
    this._srcPosition -= channelData.length;

    // Flush complete chunks
    while (this._buffer.length >= this._samplesNeeded) {
      const samples = this._buffer.splice(0, this._samplesNeeded);
      const pcm = new Int16Array(samples.length);
      for (let i = 0; i < samples.length; i++) {
        pcm[i] = Math.floor(samples[i] * 32767);
      }
      // Transfer the raw buffer to the main thread (zero-copy).
      // btoa() is not available in AudioWorkletGlobalScope — encoding happens on the main thread.
      this.port.postMessage({ type: 'pcm', buffer: pcm.buffer }, [pcm.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-capture-processor', PcmCaptureProcessor);
`;

let workletBlobUrl: string | null = null;

/**
 * Get a Blob URL for the PCM capture worklet.
 * Cached so it's only created once.
 */
export function getPcmWorkletUrl(): string {
  if (!workletBlobUrl) {
    const blob = new Blob([WORKLET_SOURCE], { type: 'application/javascript' });
    workletBlobUrl = URL.createObjectURL(blob);
  }
  return workletBlobUrl;
}
