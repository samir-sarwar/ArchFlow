export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agent?: string;
  isVoice?: boolean;
}

export interface ConversationSession {
  sessionId: string;
  name: string;
  createdAt: string;
  lastActivity: string;
  messageCount: number;
}
