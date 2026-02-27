export type WebSocketMessageType =
  | 'audio_chunk'
  | 'audio_end'
  | 'transcription'
  | 'ai_response'
  | 'diagram_update'
  | 'session_restored'
  | 'session_expired'
  | 'file_status'
  | 'file_analysis'
  | 'error';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  sessionId: string;
  payload: {
    audio?: ArrayBuffer;
    text?: string;
    diagram?: string;
    error?: string;
  };
}

export interface AudioChunkPayload {
  index: number;
  total: number;
  audio: string; // base64 LPCM
  sampleRate: number;
  bitDepth: number;
  channels: number;
}

export interface AudioEndPayload {
  totalChunks: number;
}

export interface UploadResponse {
  uploadUrl: string;
  fileKey: string;
}

export interface ExportRequest {
  sessionId: string;
  format: 'png' | 'svg' | 'mermaid';
}
