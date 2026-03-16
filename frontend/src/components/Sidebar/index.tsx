import { useUIStore } from '@/stores/uiStore';
import { useAuthStore } from '@/stores/authStore';
import { useConversationStore } from '@/stores/conversationStore';
import { useDiagramStore } from '@/stores/diagramStore';
import { useChatHistoryStore } from '@/stores/chatHistoryStore';
import {
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  MessageSquare,
  Sun,
  Moon,
  Trash2,
  LogOut,
} from 'lucide-react';
import { isToday, isYesterday, subDays, isAfter } from 'date-fns';

function groupByDate(conversations: { session_id: string; title: string; last_activity: string }[]) {
  const groups: { label: string; items: typeof conversations }[] = [
    { label: 'Today', items: [] },
    { label: 'Yesterday', items: [] },
    { label: 'Previous 7 Days', items: [] },
    { label: 'Older', items: [] },
  ];

  const sevenDaysAgo = subDays(new Date(), 7);

  for (const conv of conversations) {
    const date = new Date(conv.last_activity);
    if (isToday(date)) {
      groups[0].items.push(conv);
    } else if (isYesterday(date)) {
      groups[1].items.push(conv);
    } else if (isAfter(date, sevenDaysAgo)) {
      groups[2].items.push(conv);
    } else {
      groups[3].items.push(conv);
    }
  }

  return groups.filter((g) => g.items.length > 0);
}

export function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);

  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const conversations = useChatHistoryStore((s) => s.conversations);
  const activeId = useChatHistoryStore((s) => s.activeConversationId);

  const grouped = groupByDate(conversations);

  const sidebarItemClass =
    'w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm text-gray-500 hover:text-gray-800 hover:bg-gray-100 dark:text-white/50 dark:hover:text-white/80 dark:hover:bg-white/5 transition-colors';

  const loadConversation = (sessionId: string) => {
    useConversationStore.getState().clearMessages();
    useDiagramStore.getState().clearDiagram();
    useChatHistoryStore.getState().setActiveConversation(sessionId);

    const wsSend = useConversationStore.getState()._wsSend;
    const token = useAuthStore.getState().token;
    if (wsSend) {
      wsSend({
        action: 'restore_session',
        sessionId,
        token,
      });
      useUIStore.getState().setLoading(true);
    }
  };

  const deleteConversation = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    const wsSend = useConversationStore.getState()._wsSend;
    const token = useAuthStore.getState().token;
    if (wsSend && token) {
      wsSend({
        action: 'delete_conversation',
        sessionId,
        token,
      });
    }
    // If deleting active conversation, clear state
    if (activeId === sessionId) {
      useConversationStore.getState().resetSession();
      useDiagramStore.getState().clearDiagram();
      useChatHistoryStore.getState().setActiveConversation(null);
    }
  };

  const startNewConversation = () => {
    useConversationStore.getState().resetSession();
    useDiagramStore.getState().clearDiagram();
    useChatHistoryStore.getState().setActiveConversation(null);
  };

  const handleLogout = () => {
    useConversationStore.getState().resetSession();
    useDiagramStore.getState().clearDiagram();
    useChatHistoryStore.getState().setConversations([]);
    useChatHistoryStore.getState().setActiveConversation(null);
    logout();
  };

  return (
    <>
      {/* Toggle button — visible when sidebar is CLOSED */}
      {!sidebarOpen && (
        <button
          onClick={toggleSidebar}
          className="fixed top-4 left-4 z-30 p-2 rounded-lg glass glass-hover text-gray-400 hover:text-gray-700 dark:text-white/50 dark:hover:text-white/80 transition-colors"
          title="Open sidebar"
        >
          <PanelLeftOpen className="w-4 h-4" />
        </button>
      )}

      {/* Sidebar panel */}
      <aside
        className={`fixed top-0 left-0 h-full z-20 flex flex-col transition-transform duration-300 ease-out ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        style={{ width: '240px' }}
      >
        <div className="h-full glass-dark flex flex-col">
          {/* Header — logo + collapse button on same row */}
          <div className="px-4 pt-4 pb-4 border-b border-gray-200 dark:border-white/5">
            <div className="flex items-center gap-2.5">
              <img
                src="/assets/logodark.png"
                alt="ArchFlow"
                className="h-9 w-auto dark:hidden"
              />
              <img
                src="/assets/logolight.png"
                alt="ArchFlow"
                className="h-9 w-auto hidden dark:block"
              />
              <h1 className="text-base font-semibold text-gray-900 dark:text-white/90">ArchFlow</h1>
              <button
                onClick={toggleSidebar}
                className="ml-auto p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 dark:text-white/40 dark:hover:text-white/80 dark:hover:bg-white/5 transition-colors"
                title="Close sidebar"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* New Project button */}
          <div className="px-2 pt-3">
            <button onClick={startNewConversation} className={sidebarItemClass}>
              <Plus className="w-3.5 h-3.5" />
              New Project
            </button>
          </div>

          {/* Chat history */}
          <div className="flex-1 overflow-y-auto py-3">
            {grouped.length === 0 && (
              <div className="px-4 text-xs text-white/20">No conversations yet</div>
            )}
            {grouped.map((group) => (
              <div key={group.label} className="mb-3">
                <div className="px-4 mb-1">
                  <span className="text-[10px] font-medium text-gray-300 dark:text-white/20 uppercase tracking-wider">
                    {group.label}
                  </span>
                </div>
                <ul className="space-y-0.5 px-2">
                  {group.items.map((conv) => (
                    <li key={conv.session_id}>
                      <button
                        onClick={() => loadConversation(conv.session_id)}
                        className={`${sidebarItemClass} text-left group ${activeId === conv.session_id
                          ? 'bg-primary-500/10 text-primary-400 dark:text-primary-400'
                          : ''
                          }`}
                      >
                        <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-gray-300 group-hover:text-gray-500 dark:text-white/20 dark:group-hover:text-white/40" />
                        <span className="min-w-0 flex-1 truncate">
                          {conv.title || 'Untitled'}
                        </span>
                        <button
                          onClick={(e) => deleteConversation(e, conv.session_id)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-white/20 hover:text-red-400 transition-all"
                          title="Delete conversation"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom actions */}
          <div className="border-t border-gray-200 dark:border-white/5 p-3 space-y-1">
            <button onClick={toggleTheme} className={sidebarItemClass}>
              {theme === 'light' ? (
                <Moon className="w-3.5 h-3.5" />
              ) : (
                <Sun className="w-3.5 h-3.5" />
              )}
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </button>

            {/* User info + logout */}
            {user && (
              <div className="pt-2 border-t border-gray-200 dark:border-white/5">
                <div className="px-2 py-1 text-[11px] text-white/30 truncate">
                  {user.email}
                </div>
                <button onClick={handleLogout} className={sidebarItemClass}>
                  <LogOut className="w-3.5 h-3.5" />
                  Log Out
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
