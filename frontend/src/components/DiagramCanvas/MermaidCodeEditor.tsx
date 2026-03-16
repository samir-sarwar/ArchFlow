import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useDiagramStore } from '@/stores/diagramStore';
import { useConversationStore } from '@/stores/conversationStore';
import { Check } from 'lucide-react';

function highlightMermaid(code: string): string {
  // HTML-escape first
  let result = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Comments (%% to end of line)
  result = result.replace(/(%%.*)/g, '<span class="mermaid-comment">$1</span>');

  // Quoted strings
  result = result.replace(
    /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
    '<span class="mermaid-string">$1</span>'
  );

  // Keywords (word boundaries)
  result = result.replace(
    /\b(graph|flowchart|subgraph|end|classDef|class|style|click|sequenceDiagram|participant|actor|erDiagram|stateDiagram(?:-v2)?|gantt|pie|gitGraph|journey|direction|TD|TB|LR|RL|BT)\b/g,
    '<span class="mermaid-keyword">$1</span>'
  );

  // Arrows (escaped HTML entities for < and >)
  result = result.replace(
    /(--&gt;|==&gt;|-.+-&gt;|--[- ]+|==[= ]+|&lt;--)/g,
    '<span class="mermaid-arrow">$1</span>'
  );

  // Brackets and pipes
  result = result.replace(
    /([[\](){}|])/g,
    '<span class="mermaid-bracket">$1</span>'
  );

  return result;
}

export function MermaidCodeEditor() {
  const currentSyntax = useDiagramStore((s) => s.currentSyntax);
  const updateDiagram = useDiagramStore((s) => s.updateDiagram);
  const sessionId = useConversationStore((s) => s.sessionId);
  const wsSend = useConversationStore((s) => s._wsSend);

  const [draft, setDraft] = useState(currentSyntax);
  const gutterRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);
  const skipNextSync = useRef(false);

  const hasChanges = draft !== currentSyntax;

  const highlightedHtml = useMemo(() => highlightMermaid(draft), [draft]);

  // Sync store -> local when store changes externally (AI updates, undo/redo)
  useEffect(() => {
    if (skipNextSync.current) {
      skipNextSync.current = false;
      return;
    }
    setDraft(currentSyntax);
  }, [currentSyntax]);

  const applyChanges = useCallback(() => {
    if (draft === currentSyntax) return;

    skipNextSync.current = true;
    updateDiagram(draft, 'Manual edit');

    if (wsSend && sessionId) {
      wsSend({
        action: 'sync_diagram',
        sessionId,
        syntax: draft,
        token: localStorage.getItem('archflow_token'),
      });
    }
  }, [draft, currentSyntax, updateDiagram, wsSend, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = e.currentTarget;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const value = textarea.value;
      const newValue = value.substring(0, start) + '  ' + value.substring(end);
      setDraft(newValue);
      requestAnimationFrame(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 2;
      });
    }

    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      applyChanges();
    }
  };

  // Sync scroll: textarea -> gutter + pre
  const handleScroll = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    if (gutterRef.current) gutterRef.current.scrollTop = ta.scrollTop;
    if (preRef.current) {
      preRef.current.scrollTop = ta.scrollTop;
      preRef.current.scrollLeft = ta.scrollLeft;
    }
  };

  const lineCount = draft.split('\n').length;

  return (
    <div className="w-full h-full flex items-center justify-center p-6 md:p-10">
      {/* Card container */}
      <div className="w-full max-w-[960px] h-full max-h-[85vh] flex flex-col rounded-2xl shadow-2xl overflow-hidden bg-white/90 dark:bg-surface-200/90 border border-gray-200/60 dark:border-white/10 backdrop-blur-xl">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50/80 dark:bg-surface-400/60 border-b border-gray-200/50 dark:border-white/10 flex-shrink-0">
          <span className="text-xs text-gray-400 dark:text-white/30 font-mono">
            Mermaid
          </span>
          <div className="flex items-center gap-2">
            {hasChanges ? (
              <span className="text-xs text-amber-500 dark:text-amber-400/80">
                Unsaved changes
              </span>
            ) : currentSyntax ? (
              <span className="text-xs text-gray-400 dark:text-white/30 flex items-center gap-1">
                <Check className="w-3 h-3" />
                Saved
              </span>
            ) : null}
            <button
              onClick={applyChanges}
              disabled={!hasChanges}
              className="px-3 py-1 text-xs font-medium rounded-lg transition-colors disabled:opacity-30 disabled:cursor-default bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 dark:bg-blue-500/15 dark:hover:bg-blue-500/25 border border-blue-200 dark:border-blue-500/20"
            >
              Apply Changes
            </button>
          </div>
        </div>

        {/* Editor area */}
        <div className="flex flex-1 min-h-0">
          {/* Line numbers gutter */}
          <div
            ref={gutterRef}
            className="py-4 px-3 text-right select-none border-r border-gray-200/50 dark:border-white/10 overflow-hidden flex-shrink-0 bg-gray-50/50 dark:bg-surface-400/30"
          >
            {Array.from({ length: lineCount }, (_, i) => (
              <div
                key={i}
                className="text-xs leading-6 text-gray-400 dark:text-white/25 font-mono"
              >
                {i + 1}
              </div>
            ))}
          </div>

          {/* Textarea + Pre overlay container */}
          <div className="relative flex-1 min-h-0">
            {/* Highlighted pre (behind) */}
            <pre
              ref={preRef}
              className="code-editor-shared absolute inset-0 overflow-hidden pointer-events-none"
              aria-hidden="true"
              dangerouslySetInnerHTML={{ __html: highlightedHtml + '\n' }}
            />
            {/* Transparent textarea (on top, captures input) */}
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onScroll={handleScroll}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              className="code-editor-shared code-editor-overlay relative w-full h-full bg-transparent text-transparent caret-gray-800 dark:caret-gray-200 resize-none outline-none overflow-auto"
              placeholder={draft ? undefined : 'Enter Mermaid diagram syntax...'}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
