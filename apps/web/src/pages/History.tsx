/** History — filterable, paginated table of past generations. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  History as HistoryIcon,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Ban,
  Sparkles,
} from 'lucide-react';
import { useGenerations } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { GenerationStatus } from '@/lib/types';

const PER_PAGE = 15;

const STATUS_STYLES: Record<GenerationStatus, { bg: string; text: string }> = {
  queued: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  running: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  completed: { bg: 'bg-green-500/10', text: 'text-green-400' },
  failed: { bg: 'bg-red-500/10', text: 'text-red-400' },
  cancelled: { bg: 'bg-text-muted/10', text: 'text-text-muted' },
};

const STATUS_ICONS: Record<GenerationStatus, React.ReactNode> = {
  queued: <Clock className="h-3.5 w-3.5" />,
  running: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
  completed: <CheckCircle className="h-3.5 w-3.5" />,
  failed: <XCircle className="h-3.5 w-3.5" />,
  cancelled: <Ban className="h-3.5 w-3.5" />,
};

function StatusBadge({ status }: { status: GenerationStatus }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.queued;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        style.bg,
        style.text,
      )}
    >
      {STATUS_ICONS[status]}
      {status}
    </span>
  );
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

export function History() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [modeFilter, setModeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Simple debounce via onBlur / Enter key
  const applySearch = () => {
    setDebouncedSearch(search);
    setPage(1);
  };

  const { data, isLoading } = useGenerations({
    page,
    per_page: PER_PAGE,
    status: statusFilter || undefined,
    mode: modeFilter || undefined,
    search: debouncedSearch || undefined,
  });

  const items = data?.items ?? [];
  const totalPages = data?.pages ?? 0;
  const total = data?.total ?? 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <HistoryIcon className="h-6 w-6 text-primary-400" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Generation History</h1>
          <p className="text-sm text-text-secondary">
            {data ? `${total} generation${total !== 1 ? 's' : ''}` : 'Loading...'}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="select-field w-40"
        >
          <option value="">All statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <select
          value={modeFilter}
          onChange={(e) => {
            setModeFilter(e.target.value);
            setPage(1);
          }}
          className="select-field w-36"
        >
          <option value="">All modes</option>
          <option value="docs">Docs</option>
          <option value="skills">Skills</option>
          <option value="both">Both</option>
        </select>

        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search by repo name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onBlur={applySearch}
            onKeyDown={(e) => {
              if (e.key === 'Enter') applySearch();
            }}
            className="input-field pl-9"
          />
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-surface-border bg-surface-card py-20">
          <AlertTriangle className="mb-4 h-10 w-10 text-text-muted" />
          <p className="text-sm text-text-secondary">
            {statusFilter || modeFilter || debouncedSearch
              ? 'No generations match your filters.'
              : 'No generations yet.'}
          </p>
          {!statusFilter && !modeFilter && !debouncedSearch && (
            <Link
              to="/generate"
              className="mt-3 flex items-center gap-1.5 text-sm text-primary-400 hover:text-primary-300"
            >
              <Sparkles className="h-4 w-4" />
              Create your first generation
            </Link>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-surface-border bg-surface-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border text-left">
                  <th className="px-4 py-3 font-medium text-text-secondary">Repository</th>
                  <th className="px-4 py-3 font-medium text-text-secondary">Mode</th>
                  <th className="px-4 py-3 font-medium text-text-secondary">Status</th>
                  <th className="px-4 py-3 font-medium text-text-secondary">Model</th>
                  <th className="px-4 py-3 font-medium text-text-secondary">Duration</th>
                  <th className="px-4 py-3 font-medium text-text-secondary">Created</th>
                </tr>
              </thead>
              <tbody>
                {items.map((gen) => {
                  const repoName = gen.repo_url.replace('https://github.com/', '');
                  return (
                    <tr
                      key={gen.id}
                      className="cursor-pointer border-b border-surface-border/50 transition-colors hover:bg-surface-hover"
                    >
                      <td className="px-4 py-3">
                        <Link
                          to={`/history/${gen.id}`}
                          className="font-medium text-text-primary hover:text-primary-400"
                        >
                          {repoName}
                        </Link>
                      </td>
                      <td className="px-4 py-3 capitalize text-text-secondary">{gen.mode}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={gen.status} />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-text-secondary">
                        {gen.model}
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {formatDuration(gen.duration_ms)}
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {new Date(gen.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-surface-border px-4 py-3">
              <p className="text-sm text-text-secondary">
                Page {page} of {totalPages} ({total} total)
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="btn-secondary flex items-center gap-1 px-3 py-1.5 text-sm"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="btn-secondary flex items-center gap-1 px-3 py-1.5 text-sm"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
