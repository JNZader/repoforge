export function LoadingSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-surface-bg">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
    </div>
  );
}
