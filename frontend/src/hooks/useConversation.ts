import { useEffect, useRef, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';
import { useConversationStore } from '@/stores/conversationStore';
import { useDiagramStore } from '@/stores/diagramStore';
import { useUIStore } from '@/stores/uiStore';
import { useAuthStore } from '@/stores/authStore';
import { useChatHistoryStore, type ChatSummary } from '@/stores/chatHistoryStore';
import { createChunkPlayer, playLPCMAudio, type AudioChunkPlayer } from '@/services/audio';
import type { Message } from '@/types/conversation';
import { generateId } from '@/utils/generateId';

// Lambda WebSocket — text chat, file upload, session restore
const WS_URL = import.meta.env.VITE_WEBSOCKET_URL || '';

// Standalone voice server — Nova Sonic bidirectional streaming
// Falls back to the same WS_URL if not separately configured (monorepo local dev)
const VOICE_WS_URL = import.meta.env.VITE_VOICE_WS_URL || WS_URL;

export function useConversation() {
  const conversationStore = useConversationStore();
  const updateDiagram = useDiagramStore((s) => s.updateDiagram);
  const restoreDiagram = useDiagramStore((s) => s.restoreDiagram);
  const { setLoading, setError } = useUIStore();
  const chunkPlayerRef = useRef<AudioChunkPlayer | null>(null);
  const responseTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const repoPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Ref to hold handleIncomingMessage so the voice WS callback always uses the latest version
  const handleIncomingRef = useRef<(data: Record<string, unknown>) => void>(() => { });

  // ── Two separate WebSocket connections ──
  const token = useAuthStore((s) => s.token);
  const { isConnected, lastMessage, sendMessage: wsSend } = useWebSocket(WS_URL, undefined, token);

  // Voice WS uses direct onMessage callback to avoid React state batching
  // dropping rapid audio_chunk messages
  const voiceOnMessage = useCallback((event: MessageEvent) => {
    if (VOICE_WS_URL === WS_URL) return;
    try {
      handleIncomingRef.current(JSON.parse(event.data));
    } catch (err) {
      console.error('[ArchFlow] Failed to handle voice WS message:', err);
    }
  }, []);

  const {
    isConnected: isVoiceConnected,
    sendMessage: voiceWsSend,
  } = useWebSocket(VOICE_WS_URL, voiceOnMessage, token);

  // Cleanup audio player and polling on unmount
  useEffect(() => {
    return () => {
      chunkPlayerRef.current?.stop();
      clearTimeout(responseTimeoutRef.current);
      if (repoPollingRef.current) {
        clearInterval(repoPollingRef.current);
        repoPollingRef.current = null;
      }
    };
  }, []);

  // Share WebSocket send function and connection state via store
  useEffect(() => {
    conversationStore.setWsSend(wsSend);
  }, [wsSend]);

  useEffect(() => {
    conversationStore.setIsConnected(isConnected);
  }, [isConnected]);

  // Restore session on connect — only on fresh page load (no messages in memory).
  // Mid-session reconnects (e.g. after idle timeout during voice) keep live state.
  useEffect(() => {
    if (!isConnected) return;

    // Fetch conversation list for authenticated users
    const currentToken = useAuthStore.getState().token;
    if (currentToken) {
      wsSend({ action: 'list_conversations', token: currentToken });
    }

    const savedSessionId = localStorage.getItem('archflow_sessionId');
    if (savedSessionId) {
      const currentMessages = useConversationStore.getState().messages;
      if (currentMessages.length > 0) {
        // Reconnected mid-session — keep live frontend state
        return;
      }
      wsSend({
        action: 'restore_session',
        sessionId: savedSessionId,
        token: currentToken,
      });
      setLoading(true);
    }
  }, [isConnected]);

  // ── Repo analysis polling ──
  const startRepoPolling = (repoUrl: string, explicitSessionId?: string) => {
    // Clear any existing polling
    if (repoPollingRef.current) {
      clearInterval(repoPollingRef.current);
    }
    let attempts = 0;
    const maxAttempts = 60; // ~3 minutes at 3s intervals
    repoPollingRef.current = setInterval(() => {
      attempts += 1;
      if (attempts > maxAttempts) {
        clearInterval(repoPollingRef.current!);
        repoPollingRef.current = null;
        setLoading(false);
        setError('Repository analysis timed out. Please try again.');
        return;
      }
      wsSend({
        action: 'check_repo_status',
        sessionId: explicitSessionId || useConversationStore.getState().sessionId || '',
        repoUrl,
        token: useAuthStore.getState().token,
      });
    }, 3000);
  };

  // ── Handler shared by both sockets ──
  // Keep ref in sync so the voice WS direct callback always uses the latest closure
  const handleIncomingMessage = useCallback(
    (data: Record<string, unknown>) => {
      if (data.type === 'voice_session_started') {
        if (data.sessionId) {
          conversationStore.setSessionId(data.sessionId as string);
        }
      }

      if (data.type === 'voice_transcription') {
        conversationStore.updateLastUserMessage((data.payload as { text: string }).text);
      }

      if (data.type === 'voice_status') {
        const p = data.payload as { stage: string; message: string };
        conversationStore.setVoiceStatus({ stage: p.stage, message: p.message });
      }

      if (data.type === 'ai_response') {
        if (data.sessionId) {
          conversationStore.setSessionId(data.sessionId as string);
        }

        const payload = data.payload as {
          transcription?: string;
          text: string;
          agent: string;
          diagram?: string;
          audioUrl?: string;
          hasAudio?: boolean;
        };

        if (payload.transcription) {
          conversationStore.updateLastUserMessage(payload.transcription);
        }

        const assistantMsg: Message = {
          role: 'assistant',
          content: payload.text,
          timestamp: new Date().toISOString(),
          agent: payload.agent,
          isVoice: !!payload.hasAudio || !!payload.transcription,
        };
        conversationStore.addMessage(assistantMsg);

        if (payload.diagram) {
          updateDiagram(payload.diagram, payload.text);
        }

        // Voice diagram generation is handled by Nova Sonic tool use (generateDiagram)
        // — no need to forward transcription to Lambda.

        if (payload.audioUrl) {
          conversationStore.setAudioPlaying(true);
          playLPCMAudio(payload.audioUrl, 24000, (_playing) => {
            conversationStore.setAudioPlaying(false);
          }).catch((err) => {
            console.error('[ArchFlow] Audio playback failed:', err);
            conversationStore.setAudioPlaying(false);
          });
        }

        clearTimeout(responseTimeoutRef.current);
        conversationStore.setVoiceStatus(null);
        setLoading(false);
        setError(null);
      }

      if (data.type === 'audio_chunk') {
        // Create player lazily on first chunk — chunks arrive BEFORE ai_response
        if (!chunkPlayerRef.current) {
          chunkPlayerRef.current = createChunkPlayer(24000, (playing) => {
            conversationStore.setAudioPlaying(playing);
          });
        }
        chunkPlayerRef.current.addChunk(
          (data.payload as { audio: string }).audio,
        );
      }

      if (data.type === 'audio_end') {
        chunkPlayerRef.current?.finish();
      }

      if (data.type === 'session_restored') {
        const payload = data.payload as {
          messages: Message[];
          currentDiagram?: string;
          diagramVersions?: unknown[];
        };
        conversationStore.restoreSession({
          messages: payload.messages,
          sessionId: data.sessionId as string,
        });
        if (payload.currentDiagram) {
          restoreDiagram(payload.currentDiagram, (payload.diagramVersions as []) || []);
        }
        useChatHistoryStore.getState().setActiveConversation(data.sessionId as string);
        clearTimeout(responseTimeoutRef.current);
        setLoading(false);
      }

      if (data.type === 'conversations_list') {
        const payload = data.payload as { conversations: ChatSummary[] };
        useChatHistoryStore.getState().setConversations(payload.conversations || []);
      }

      if (data.type === 'conversation_deleted') {
        const payload = data.payload as { sessionId: string };
        useChatHistoryStore.getState().removeConversation(payload.sessionId);
      }

      if (data.type === 'session_expired') {
        localStorage.removeItem('archflow_sessionId');
        conversationStore.clearMessages();
        clearTimeout(responseTimeoutRef.current);
        setLoading(false);
      }

      if (data.type === 'file_status') {
        const p = data.payload as { status: string; message?: string };
        if (p.status === 'error') {
          setError(p.message || 'File processing failed');
        }
      }

      if (data.type === 'file_analysis') {
        const p = data.payload as {
          fileKey?: string;
          fileName?: string;
          summary?: string;
          diagram?: string;
        };
        const analysisMsg: Message = {
          role: 'assistant',
          content: `**File analyzed: ${p.fileName || 'document'}**\n\n${p.summary || 'Analysis complete.'}`,
          timestamp: new Date().toISOString(),
          agent: 'context_analyzer',
        };
        conversationStore.addMessage(analysisMsg);
        if (p.diagram) {
          updateDiagram(p.diagram, 'Generated from uploaded file');
        }
        if (p.fileKey) {
          window.dispatchEvent(new CustomEvent('archflow:file-ready', { detail: { fileKey: p.fileKey } }));
        }
        clearTimeout(responseTimeoutRef.current);
        setLoading(false);
      }

      if (data.type === 'repo_analysis') {
        const p = data.payload as {
          repoUrl?: string;
          repoName?: string;
          summary?: string;
          contextPreview?: string;
        };

        // Build message with context preview for debugging
        let content = `**Repository analyzed: ${p.repoName || 'repo'}**\n\n${p.summary || 'Analysis complete. You can now ask questions about this repository or request architecture diagrams based on it.'}`;
        if (p.contextPreview) {
          content += `\n\n<details><summary>Context Preview (what the AI sees)</summary>\n\n\`\`\`\n${p.contextPreview}\n\`\`\`\n\n</details>`;
        }

        const analysisMsg: Message = {
          role: 'assistant',
          content,
          timestamp: new Date().toISOString(),
          agent: 'repo_analyzer',
        };
        conversationStore.addMessage(analysisMsg);
        if (data.sessionId) {
          conversationStore.setSessionId(data.sessionId as string);
        }
        // Stop polling if active
        if (repoPollingRef.current) {
          clearInterval(repoPollingRef.current);
          repoPollingRef.current = null;
        }
        clearTimeout(responseTimeoutRef.current);
        setLoading(false);
      }

      if (data.type === 'repo_analysis_started') {
        const p = data.payload as { repoUrl?: string; repoName?: string };
        const analysisMsg: Message = {
          role: 'assistant',
          content: `Analyzing repository: **${p.repoName || p.repoUrl}**... This may take a moment.`,
          timestamp: new Date().toISOString(),
          agent: 'repo_analyzer',
        };
        conversationStore.addMessage(analysisMsg);
        if (data.sessionId) {
          conversationStore.setSessionId(data.sessionId as string);
        }
        // Start polling for results — pass sessionId explicitly to avoid stale closure
        const sid = (data.sessionId as string) || useConversationStore.getState().sessionId || '';
        startRepoPolling(p.repoUrl || '', sid);
      }

      // repo_analysis_pending — no-op, keep polling


      if (data.type === 'diagram_update') {
        const p = data.payload as { diagram?: string };
        if (p?.diagram) {
          updateDiagram(p.diagram, 'Diagram update');
        }
      }

      if (data.type === 'error') {
        // Stop repo polling on error
        if (repoPollingRef.current) {
          clearInterval(repoPollingRef.current);
          repoPollingRef.current = null;
        }
        console.error('[ArchFlow] Backend error:', data.payload);
        clearTimeout(responseTimeoutRef.current);
        conversationStore.setVoiceStatus(null);

        // Only overwrite the last user message if it was a voice placeholder
        const msgs = useConversationStore.getState().messages;
        const lastUserMsg = [...msgs].reverse().find((m) => m.role === 'user');
        if (lastUserMsg?.isVoice) {
          conversationStore.updateLastUserMessage('[Voice message failed]');
        }

        setError((data.payload as { message: string }).message);
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  // Keep ref in sync for the voice WS direct callback
  handleIncomingRef.current = handleIncomingMessage;

  // Handle messages from the Lambda text WebSocket
  useEffect(() => {
    if (!lastMessage?.data) return;
    try {
      handleIncomingMessage(JSON.parse(lastMessage.data));
    } catch (err) {
      console.error('[ArchFlow] Failed to handle text WS message:', err, lastMessage?.data);
      clearTimeout(responseTimeoutRef.current);
      setError('Failed to parse server response');
      setLoading(false);
    }
  }, [lastMessage]);

  // Voice WS messages are handled via direct onMessage callback (see voiceOnMessage above)
  // to avoid React state batching dropping rapid audio_chunk messages.

  // ── Text message ──
  const GITHUB_MENTION_RE = /@github:\s*(https?:\/\/(?:www\.)?github\.com\/[\w.-]+\/[\w.-]+)/i;

  const sendMessage = (content: string) => {
    if (!content.trim()) return;

    // Detect @github:<url> anywhere in the message — route to github_repo action
    const mentionMatch = content.match(GITHUB_MENTION_RE);
    if (mentionMatch) {
      const repoUrl = mentionMatch[1].replace(/[\x00-\x1F\x7F]/g, '').trim();
      if (repoUrl) {
        const userMsg: Message = {
          role: 'user',
          content: `Analyzing GitHub repository: ${repoUrl}`,
          timestamp: new Date().toISOString(),
        };
        conversationStore.addMessage(userMsg);

        const sent = wsSend({
          action: 'github_repo',
          sessionId: useConversationStore.getState().sessionId || '',
          repoUrl,
          token: useAuthStore.getState().token,
        });

        if (!sent) {
          setError('Not connected to the server. Reconnecting...');
          return;
        }

        setLoading(true);
        setError(null);
        return;
      }
    }

    const userMsg: Message = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    conversationStore.addMessage(userMsg);

    const currentDiagram = useDiagramStore.getState().currentSyntax;

    // Route through Sonic (voice WS) when available — much faster + better quality.
    // Falls back to Lambda WS (Nova Lite) if voice server is not connected.
    const useVoiceWs = isVoiceConnected && VOICE_WS_URL !== WS_URL;

    let sent = false;
    if (useVoiceWs) {
      sent = voiceWsSend({
        event: {
          text_message: {
            sessionId: conversationStore.sessionId,
            text: content,
            currentDiagram: currentDiagram || undefined,
          },
        },
      });
    }

    // Fallback to Lambda if voice WS send failed or not available
    if (!sent) {
      sent = wsSend({
        action: 'message',
        sessionId: conversationStore.sessionId,
        text: content,
        currentDiagram: currentDiagram || undefined,
        token: useAuthStore.getState().token,
      });
    }

    if (!sent) {
      setError('Not connected to the server. Reconnecting...');
      return;
    }

    setLoading(true);
    setError(null);

    // Safety timeout for text messages — prevents permanent loading state
    clearTimeout(responseTimeoutRef.current);
    responseTimeoutRef.current = setTimeout(() => {
      setLoading(false);
      setError('Response timed out. Please try again.');
    }, 45_000);
  };

  // ── Streaming voice session ──
  // These events go to the voice server's WebSocket, NOT the Lambda one.
  const audioSeqRef = useRef(0);
  // Tracks state sent to the voice server so we can send the proper Nova Sonic events
  const promptNameRef = useRef<string>('');
  const audioContentNameRef = useRef<string>('');

  /** Start a streaming voice session — sends the Nova Sonic event sequence to the voice server. */
  const startVoiceSession = useCallback(() => {
    const currentDiagram = useDiagramStore.getState().currentSyntax;
    audioSeqRef.current = 0;

    const promptName = generateId();
    const audioContentName = generateId();
    const systemContentName = generateId();
    promptNameRef.current = promptName;
    audioContentNameRef.current = audioContentName;

    let currentSessionId = useConversationStore.getState().sessionId;
    if (!currentSessionId) {
      currentSessionId = generateId();
      conversationStore.setSessionId(currentSessionId);
    }


    const userMsg: Message = {
      role: 'user',
      content: '[Listening...]',
      timestamp: new Date().toISOString(),
      isVoice: true,
    };
    conversationStore.addMessage(userMsg);
    setError(null);

    // 1. Session start
    voiceWsSend({
      event: {
        sessionStart: {
          sessionId: currentSessionId,
          inferenceConfiguration: { maxTokens: 1024, topP: 0.95, temperature: 0.7 }
        }
      }
    });

    // 2. Prompt start — text + audio output.
    // AudioOutputConfiguration is REQUIRED by Nova Sonic\u2019s API.
    // Audio chunks will be received if awscrt delivers them, and browser TTS
    // speaks the text response as a fallback regardless.
    voiceWsSend({
      event: {
        promptStart: {
          promptName,
          textOutputConfiguration: { mediaType: 'text/plain' },
          audioOutputConfiguration: {
            mediaType: 'audio/lpcm',
            sampleRateHertz: 24000,
            sampleSizeBits: 16,
            channelCount: 1,
            voiceId: 'tiffany',
            encoding: 'base64',
            audioType: 'SPEECH',
          },
          toolUseOutputConfiguration: { mediaType: 'application/json' },
          toolConfiguration: {
            tools: [{
              toolSpec: {
                name: 'generateDiagram',
                description:
                  'Generate or update a Mermaid.js architecture diagram. ' +
                  'Call this whenever the user asks to create, modify, visualize, ' +
                  'or diagram a software architecture.',
                inputSchema: {
                  json: JSON.stringify({
                    type: 'object',
                    properties: {
                      request: {
                        type: 'string',
                        description:
                          'What to diagram, including any specific components, ' +
                          'services, patterns, or modifications to the existing diagram',
                      },
                    },
                    required: ['request'],
                  }),
                },
              },
            }],
          },
        },
      },
    });


    // 3. System prompt (context-aware: include current diagram)
    let systemPrompt =
      'You are ArchFlow, an expert AI software architect. ' +
      'You help users design software system architecture through natural conversation. ' +
      'When the user asks you to create, modify, visualize, or diagram any software architecture, ' +
      'use the generateDiagram tool. Briefly describe what you plan to create, then call the tool. ' +
      'After receiving the tool result, summarize what was created in the diagram. ' +
      'If uploaded file context is provided below, use it as primary input for your advice — ' +
      'reference specific components, technologies, and requirements from the analysis. ' +
      'Keep your spoken responses conversational and under 4-5 sentences so they feel natural when heard aloud.';
    if (currentDiagram) {
      systemPrompt += `\n\nCurrent architecture diagram:\n${currentDiagram}`;
    }

    voiceWsSend({ event: { contentStart: { promptName, contentName: systemContentName, type: 'TEXT', interactive: false, role: 'SYSTEM', textInputConfiguration: { mediaType: 'text/plain' } } } });
    voiceWsSend({ event: { textInput: { promptName, contentName: systemContentName, content: systemPrompt } } });
    voiceWsSend({ event: { contentEnd: { promptName, contentName: systemContentName } } });

    // 4. Audio content start
    voiceWsSend({
      event: {
        contentStart: {
          promptName,
          contentName: audioContentName,
          type: 'AUDIO',
          interactive: true,
          role: 'USER',
          audioInputConfiguration: {
            mediaType: 'audio/lpcm',
            sampleRateHertz: 16000,
            sampleSizeBits: 16,
            channelCount: 1,
            audioType: 'SPEECH',
            encoding: 'base64',
          },
        },
      },
    });
  }, [voiceWsSend, conversationStore, setError, wsSend]);

  /** Send a single PCM audio chunk (base64) to the voice server. */
  const sendAudioChunk = useCallback(
    (pcmBase64: string) => {
      audioSeqRef.current += 1;
      voiceWsSend({
        event: {
          audioInput: {
            promptName: promptNameRef.current,
            contentName: audioContentNameRef.current,
            content: pcmBase64,
          },
        },
      });
    },
    [voiceWsSend],
  );

  /** End the streaming voice session — sends only contentEnd (end of audio input).
   *
   * NOTE: We do NOT send promptEnd or sessionEnd here.
   * The server sends those to Bedrock automatically after it receives
   * completionEnd, which is when Bedrock has finished generating the response.
   * Sending promptEnd/sessionEnd immediately from the browser was killing the
   * Nova Sonic stream before the response could be delivered.
   */
  const stopVoiceSession = useCallback(() => {
    const promptName = promptNameRef.current;
    const audioContentName = audioContentNameRef.current;

    // Signal end of audio input to Bedrock — server + Bedrock do the rest
    voiceWsSend({ event: { contentEnd: { promptName, contentName: audioContentName } } });

    setLoading(true);

    // Safety timeout — server should respond well within 30 s
    clearTimeout(responseTimeoutRef.current);
    responseTimeoutRef.current = setTimeout(() => {
      conversationStore.setVoiceStatus(null);
      setLoading(false);
      setError('Voice processing timed out. Please try again.');
    }, 30_000);
  }, [voiceWsSend, conversationStore, setLoading, setError]);


  const stopAudioPlayback = () => {
    chunkPlayerRef.current?.stop();
  };

  return {
    messages: conversationStore.messages,
    sessionId: conversationStore.sessionId,
    isRecording: conversationStore.isRecording,
    isConnected,
    isVoiceConnected,
    sendMessage,
    startVoiceSession,
    sendAudioChunk,
    stopVoiceSession,
    stopAudioPlayback,
    sendWsMessage: wsSend,
  };
}
