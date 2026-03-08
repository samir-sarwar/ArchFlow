import { useEffect } from 'react';

interface ToastProps {
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  onDismiss: () => void;
  duration?: number;
}

const typeStyles = {
  info: 'bg-primary-50 text-primary-700 border-primary-200 dark:bg-primary-600/20 dark:text-primary-200 dark:border-primary-500/20',
  success: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-600/20 dark:text-green-200 dark:border-green-500/20',
  warning: 'bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-600/20 dark:text-yellow-200 dark:border-yellow-500/20',
  error: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-600/20 dark:text-red-200 dark:border-red-500/20',
};

export function Toast({ message, type, onDismiss, duration = 5000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [onDismiss, duration]);

  return (
    <div
      className={`flex items-center gap-2 px-4 py-3 rounded-xl border text-sm shadow-lg shadow-gray-300/20 dark:shadow-black/20 backdrop-blur-xl animate-slide-up ${typeStyles[type]}`}
    >
      <span className="flex-1">{message}</span>
      <button onClick={onDismiss} className="opacity-60 hover:opacity-100 transition-opacity">
        &times;
      </button>
    </div>
  );
}
