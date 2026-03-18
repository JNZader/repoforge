/** Generate page — placeholder for commit 1, expanded in commit 2. */

import { Sparkles } from 'lucide-react';

export function Generate() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <Sparkles className="h-6 w-6 text-primary-400" />
        <h1 className="text-2xl font-bold text-text-primary">Generate Documentation & Skills</h1>
      </div>
      <div className="rounded-lg border border-surface-border bg-surface-card p-12 text-center">
        <p className="text-text-secondary">Generation form loading...</p>
      </div>
    </div>
  );
}
