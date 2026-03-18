/** Dashboard — summary stats + recent generations + CTA. */

import { Link } from 'react-router-dom';
import {
  Sparkles,
  TrendingUp,
  Clock,
  Coins,
  CheckCircle,
  XCircle,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { useAnalyticsSummary, useGenerations } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { Generation, GenerationStatus } from '@/lib/types';

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

const statusColors: Record<GenerationStatus, string> = {
  queued: 'text-yellow-400',
  running: 'text-blue-400',
  completed: 'text-green-400',
  failed: 'text-red-400',
  cancelled: 'text-text-muted',
};

const statusIcons: Record<GenerationStatus, React.ReactNode> = {
  queued: <Clock className="h-4 w-4" />,
  running: <Loader2 className="h-4 w-4 animate-spin" />,
  completed: <CheckCircle className="h-4 w-4" />,
  failed: <XCircle className="h-4 w-4" />,
  cancelled: <XCircle className="h-4 w-4" />,
};

function StatCard({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-secondary">{label}</p>
        <div className="text-primary-400">{icon}</div>
      </div>
      <p className="mt-2 text-2xl font-bold text-text-primary">{value}</p>
    </div>
  );
}

function RecentRow({ gen }: { gen: Generation }) {
  const repoName = gen.repo_url.replace('https://github.com/', '');
  return (
    <Link
      to={`/generate/${gen.id}`}
      className="flex items-center gap-3 rounded-lg px-3 py-3 transition-colors hover:bg-surface-hover"
    >
      <div className={cn('shrink-0', statusColors[gen.status])}>
        {statusIcons[gen.status]}
      </div>
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium text-text-primary">{repoName}</p>
        <p className="text-xs text-text-secondary">
          {gen.mode} &middot; {gen.model} &middot;{' '}
          {new Date(gen.created_at).toLocaleDateString()}
        </p>
      </div>
      {gen.duration_ms && (
        <span className="text-xs text-text-muted">{formatDuration(gen.duration_ms)}</span>
      )}
    </Link>
  );
}

export function Dashboard() {
  const { data: summary, isLoading: summaryLoading } = useAnalyticsSummary();
  const { data: generations, isLoading: gensLoading } = useGenerations({ per_page: 5 });

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-sm text-text-secondary">Overview of your generation activity</p>
        </div>
        <Link
          to="/generate"
          className="btn-primary flex items-center gap-2"
        >
          <Sparkles className="h-4 w-4" />
          Generate Now
        </Link>
      </div>

      {/* Stats Grid */}
      {summaryLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-card" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Total Generations"
            value={formatNumber(summary.total_generations)}
            icon={<Sparkles className="h-5 w-5" />}
          />
          <StatCard
            label="Success Rate"
            value={`${Math.round(summary.success_rate)}%`}
            icon={<TrendingUp className="h-5 w-5" />}
          />
          <StatCard
            label="Avg Duration"
            value={formatDuration(summary.avg_duration_ms)}
            icon={<Clock className="h-5 w-5" />}
          />
          <StatCard
            label="Total Tokens"
            value={formatNumber(summary.total_tokens)}
            icon={<Coins className="h-5 w-5" />}
          />
        </div>
      ) : null}

      {/* Recent Generations */}
      <div className="rounded-lg border border-surface-border bg-surface-card">
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-4">
          <h2 className="font-semibold text-text-primary">Recent Generations</h2>
          <Link
            to="/history"
            className="flex items-center gap-1 text-sm text-primary-400 hover:text-primary-300"
          >
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <div className="divide-y divide-surface-border px-2 py-1">
          {gensLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
            </div>
          ) : generations?.items.length ? (
            generations.items.map((gen) => <RecentRow key={gen.id} gen={gen} />)
          ) : (
            <div className="py-12 text-center">
              <Sparkles className="mx-auto mb-3 h-10 w-10 text-text-muted" />
              <p className="text-sm text-text-secondary">No generations yet</p>
              <Link to="/generate" className="mt-2 inline-block text-sm text-primary-400 hover:text-primary-300">
                Create your first one
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
