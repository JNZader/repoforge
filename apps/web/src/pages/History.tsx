/** History — placeholder page for lazy loading. */

import { History as HistoryIcon } from 'lucide-react';

export function History() {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center gap-3 mb-6">
        <HistoryIcon className="h-6 w-6 text-primary-400" />
        <h1 className="text-2xl font-bold text-text-primary">Generation History</h1>
      </div>
      <div className="rounded-lg border border-surface-border bg-surface-card p-12 text-center">
        <p className="text-text-secondary">History page — coming in Phase 9</p>
      </div>
    </div>
  );
}
