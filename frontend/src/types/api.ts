export type WebSocketMessageType =
  | 'audio_chunk'
  | 'transcription'
  | 'ai_response'
  | 'diagram_update'
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

export interface UploadResponse {
  uploadUrl: string;
  fileKey: string;
}

export interface ExportRequest {
  sessionId: string;
  format: 'png' | 'svg' | 'mermaid';
}
