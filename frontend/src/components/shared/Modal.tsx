import type { ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}

export function Modal({ open, onOpenChange, title, children }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 dark:bg-black/60 backdrop-blur-sm" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 glass-dark rounded-2xl p-6 shadow-2xl shadow-gray-300/30 dark:shadow-black/40 max-w-md w-full border border-gray-200 dark:border-white/10">
          <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-white/90 mb-4">
            {title}
          </Dialog.Title>
          {children}
          <Dialog.Close className="absolute top-3 right-3 text-gray-300 hover:text-gray-600 dark:text-white/30 dark:hover:text-white/60 transition-colors">
            &times;
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
