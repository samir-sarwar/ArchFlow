import { useEffect } from 'react';
import { Mail, X, AlertTriangle } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';
import { DEMO_CONTACT_EMAIL, DEMO_MAILTO } from '@/utils/credits';

export function CreditsExhaustedModal() {
  const open = useUIStore((s) => s.creditsExhaustedOpen);
  const setOpen = useUIStore((s) => s.setCreditsExhaustedOpen);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, setOpen]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="credits-modal-title"
    >
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-fade-in"
        onClick={() => setOpen(false)}
      />

      <div
        className="relative w-full max-w-md rounded-2xl border bg-red-50 text-red-700 border-red-200 dark:bg-red-600/20 dark:text-red-200 dark:border-red-500/30 shadow-2xl shadow-red-900/20 backdrop-blur-xl animate-slide-up p-6"
      >
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="absolute top-3 right-3 p-1 rounded-full opacity-60 hover:opacity-100 transition-opacity"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-start gap-3">
          <div className="shrink-0 mt-0.5">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h2
              id="credits-modal-title"
              className="text-base font-semibold leading-snug"
            >
              Sorry! Due to the influx of users we&apos;ve ran out of AWS credits.
            </h2>
            <p className="mt-2 text-sm leading-relaxed opacity-90">
              To demo ArchFlow, contact me at{' '}
              <a
                href={DEMO_MAILTO}
                className="underline font-medium hover:opacity-80"
              >
                {DEMO_CONTACT_EMAIL}
              </a>
              .
            </p>

            <a
              href={DEMO_MAILTO}
              className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors shadow-md shadow-red-900/20"
            >
              <Mail className="w-4 h-4" />
              Click me to email
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
