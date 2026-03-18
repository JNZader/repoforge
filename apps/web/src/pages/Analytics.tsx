/** Analytics — placeholder page. */

import { BarChart3 } from 'lucide-react';

export function Analytics() {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-center gap-3 mb-6">
        <BarChart3 className="h-6 w-6 text-primary-400" />
        <h1 className="text-2xl font-bold text-text-primary">Analytics</h1>
      </div>
      <div className="rounded-lg border border-surface-border bg-surface-card p-12 text-center">
        <p className="text-text-secondary">Analytics dashboard — coming in Phase 9</p>
      </div>
    </div>
  );
}
