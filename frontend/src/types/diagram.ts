export type DiagramType = 'flowchart' | 'sequence' | 'er' | 'c4';

export type EditorMode = 'voice' | 'manual';

export interface DiagramVersion {
  version: number;
  syntax: string;
  timestamp: string;
  description?: string;
}

export interface DiagramState {
  syntax: string;
  diagramType: DiagramType;
  isValid: boolean;
  errorMessage?: string;
}
