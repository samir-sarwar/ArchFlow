export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-4">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-200 dark:border-white/10 border-t-primary-500" />
    </div>
  );
}
