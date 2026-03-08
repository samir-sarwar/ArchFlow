import { useUIStore } from '@/stores/uiStore';
import { useConversationStore } from '@/stores/conversationStore';
import {
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Plus,
  MessageSquare,
  Sun,
  Moon,
} from 'lucide-react';

const PLACEHOLDER_CHATS = [
  { id: '1', title: 'Inventory System', date: 'Today' },
  { id: '2', title: 'Payment V2 Gateway', date: 'Yesterday' },
  { id: '3', title: 'Team Settings', date: '3 days ago' },
];

export function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);

  const sidebarItemClass =
    'w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm text-gray-500 hover:text-gray-800 hover:bg-gray-100 dark:text-white/50 dark:hover:text-white/80 dark:hover:bg-white/5 transition-colors';

  return (
    <>
      {/* Toggle button — always visible */}
      <button
        onClick={toggleSidebar}
        className="fixed top-4 left-4 z-30 p-2 rounded-lg glass glass-hover text-gray-400 hover:text-gray-700 dark:text-white/50 dark:hover:text-white/80 transition-colors"
        title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
      >
        {sidebarOpen ? (
          <PanelLeftClose className="w-4 h-4" />
        ) : (
          <PanelLeftOpen className="w-4 h-4" />
        )}
      </button>

      {/* Sidebar panel */}
      <aside
        className={`fixed top-0 left-0 h-full z-20 flex flex-col transition-transform duration-300 ease-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ width: '240px' }}
      >
        <div className="h-full glass-dark flex flex-col">
          {/* Header */}
          <div className="px-4 pt-14 pb-4 border-b border-gray-200 dark:border-white/5">
            <h1 className="text-base font-semibold text-gray-900 dark:text-white/90">ArchFlow</h1>
          </div>

          {/* Past Chats */}
          <div className="flex-1 overflow-y-auto py-3">
            <div className="px-4 mb-2">
              <span className="text-[10px] font-medium text-gray-300 dark:text-white/20 uppercase tracking-wider">
                Past Chats
              </span>
            </div>
            <ul className="space-y-0.5 px-2">
              {PLACEHOLDER_CHATS.map((chat) => (
                <li key={chat.id}>
                  <button className={`${sidebarItemClass} text-left group`}>
                    <MessageSquare className="w-3.5 h-3.5 text-gray-300 group-hover:text-gray-500 dark:text-white/20 dark:group-hover:text-white/40 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <span className="block truncate">{chat.title}</span>
                      <span className="text-[10px] text-gray-300 dark:text-white/20">
                        {chat.date}
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Bottom actions */}
          <div className="border-t border-gray-200 dark:border-white/5 p-3 space-y-1">
            <button
              onClick={() => {
                useConversationStore.getState().resetSession();
                window.location.reload();
              }}
              className={sidebarItemClass}
            >
              <Plus className="w-3.5 h-3.5" />
              New Project
            </button>
            <button className={sidebarItemClass}>
              <Settings className="w-3.5 h-3.5" />
              Settings
            </button>
            <button
              onClick={toggleTheme}
              className={sidebarItemClass}
            >
              {theme === 'light' ? (
                <Moon className="w-3.5 h-3.5" />
              ) : (
                <Sun className="w-3.5 h-3.5" />
              )}
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
