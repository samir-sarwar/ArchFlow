export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  agent?: string;
}

export interface ConversationSession {
  sessionId: string;
  name: string;
  createdAt: string;
  lastActivity: string;
  messageCount: number;
}
