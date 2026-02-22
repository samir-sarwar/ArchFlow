import { VoiceRecorder } from './VoiceRecorder';
import { ConversationDisplay } from './ConversationDisplay';

export function VoiceInterface() {
  return (
    <>
      <ConversationDisplay />
      <VoiceRecorder />
    </>
  );
}

export { VoiceRecorder } from './VoiceRecorder';
export { AudioVisualizer } from './AudioVisualizer';
export { ConversationDisplay } from './ConversationDisplay';
