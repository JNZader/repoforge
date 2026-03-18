/** HistoryDetail — full generation detail with metadata, events, download, delete. */

import { useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ExternalLink,
  Download,
  Trash2,
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  Ban,
  FileText,
  Coins,
  Timer,
  Star,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useGeneration, useDeleteGeneration } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { GenerationStatus } from '@/lib/types';

const API_URL = import.meta.env.VITE_API_URL ?? '';

const STATUS_STYLES: Record<GenerationStatus, { bg: string; text: string; label: string }> = {
  queued: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', label: 'Queued' },
  running: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'Running' },
  completed: { bg: 'bg-green-500/10', text: 'text-green-400', label: 'Completed' },
  failed: { bg: 'bg-red-500/10', text: 'text-red-400', label: 'Failed' },
  cancelled: { bg: 'bg-text-muted/10', text: 'text-text-muted', label: 'Cancelled' },
};

const STATUS_ICONS: Record<GenerationStatus, React.ReactNode> = {
  queued: <Clock className="h-4 w-4" />,
  running: <Loader2 className="h-4 w-4 animate-spin" />,
  completed: <CheckCircle className="h-4 w-4" />,
  failed: <XCircle className="h-4 w-4" />,
  cancelled: <Ban className="h-4 w-4" />,
};

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

function formatNumber(n: number | null): string {
  if (n == null) return '-';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function MetaCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-4">
      <div className="flex items-center gap-2 text-text-secondary">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className="mt-1.5 text-lg font-bold text-text-primary">{value}</p>
    </div>
  );
}

export function HistoryDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: gen, isLoading } = useGeneration(id);
  const deleteMutation = useDeleteGeneration();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showEvents, setShowEvents] = useState(false);

  const handleDelete = () => {
    if (!id) return;
    deleteMutation.mutate(id, {
      onSuccess: () => navigate('/history'),
    });
  };

  const handleDownload = () => {
    if (!id) return;
    const token = localStorage.getItem('repoforge_token');
    const url = `${API_URL}/api/generate/${id}/download`;
    window.open(token ? `${url}?token=${encodeURIComponent(token)}` : url, '_blank');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (!gen) {
    return (
      <div className="mx-auto max-w-3xl py-20 text-center">
        <p className="text-text-secondary">Generation not found.</p>
        <Link to="/history" className="mt-2 inline-block text-sm text-primary-400">
          Back to history
        </Link>
      </div>
    );
  }

  const repoName = gen.repo_url.replace('https://github.com/', '');
  const statusInfo = STATUS_STYLES[gen.status] ?? STATUS_STYLES.queued;
  const metadata = gen.result_metadata ?? {};
  const qualityScore = metadata.quality_score as number | undefined;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Back link */}
      <Link
        to="/history"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to history
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium',
                statusInfo.bg,
                statusInfo.text,
              )}
            >
              {STATUS_ICONS[gen.status]}
              {statusInfo.label}
            </span>
            <span className="text-sm capitalize text-text-secondary">{gen.mode}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-text-primary">{repoName}</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Created {new Date(gen.created_at).toLocaleString()}
            {gen.completed_at && ` · Completed ${new Date(gen.completed_at).toLocaleString()}`}
          </p>
        </div>

        <div className="flex gap-2">
          {gen.status === 'completed' && (
            <button type="button" onClick={handleDownload} className="btn-primary flex items-center gap-2">
              <Download className="h-4 w-4" />
              Download ZIP
            </button>
          )}
          {showDeleteConfirm ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-red-400">Are you sure?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="btn-danger flex items-center gap-1.5 px-3 py-1.5 text-sm"
              >
                {deleteMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                Yes, delete
              </button>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="btn-secondary px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="btn-secondary flex items-center gap-2 text-red-400 hover:text-red-300"
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {gen.error_message && (
        <div className="rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="mt-1 text-sm text-red-300">{gen.error_message}</p>
          {gen.error_id && (
            <p className="mt-1 font-mono text-xs text-red-400/60">Error ID: {gen.error_id}</p>
          )}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetaCard
          label="Files Generated"
          value={gen.files_generated != null ? String(gen.files_generated) : '-'}
          icon={<FileText className="h-4 w-4" />}
        />
        <MetaCard
          label="Total Tokens"
          value={formatNumber(gen.total_tokens)}
          icon={<Coins className="h-4 w-4" />}
        />
        <MetaCard
          label="Duration"
          value={formatDuration(gen.duration_ms)}
          icon={<Timer className="h-4 w-4" />}
        />
        <MetaCard
          label="Quality Score"
          value={qualityScore != null ? `${Math.round(qualityScore * 100)}%` : '-'}
          icon={<Star className="h-4 w-4" />}
        />
      </div>

      {/* Configuration Details */}
      <div className="rounded-lg border border-surface-border bg-surface-card">
        <div className="border-b border-surface-border px-5 py-4">
          <h2 className="font-semibold text-text-primary">Configuration</h2>
        </div>
        <div className="grid grid-cols-1 gap-0 sm:grid-cols-2">
          {[
            { label: 'Repository URL', value: gen.repo_url, link: true },
            { label: 'Mode', value: gen.mode },
            { label: 'Model', value: gen.model },
            { label: 'Provider', value: gen.provider },
            { label: 'Language', value: gen.language },
            { label: 'Status', value: gen.status },
          ].map((item) => (
            <div
              key={item.label}
              className="flex items-baseline justify-between border-b border-surface-border/50 px-5 py-3"
            >
              <span className="text-sm text-text-secondary">{item.label}</span>
              {item.link ? (
                <a
                  href={item.value}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-primary-400 hover:text-primary-300"
                >
                  {(item.value as string).replace('https://github.com/', '')}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : (
                <span className="text-sm font-medium capitalize text-text-primary">
                  {item.value}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Result Metadata */}
      {Object.keys(metadata).length > 0 && (
        <div className="rounded-lg border border-surface-border bg-surface-card">
          <div className="border-b border-surface-border px-5 py-4">
            <h2 className="font-semibold text-text-primary">Result Metadata</h2>
          </div>
          <div className="px-5 py-4">
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-surface-bg p-4 font-mono text-xs text-text-secondary">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Event Timeline (expandable) */}
      <div className="rounded-lg border border-surface-border bg-surface-card">
        <button
          type="button"
          onClick={() => setShowEvents(!showEvents)}
          className="flex w-full items-center gap-2 px-5 py-4 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
        >
          {showEvents ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          Event Timeline
        </button>
        {showEvents && (
          <div className="border-t border-surface-border px-5 py-4">
            <p className="text-sm text-text-muted">
              Event timeline is populated during generation and displayed on the live view page.
              Navigate to{' '}
              <Link to={`/generate/${gen.id}`} className="text-primary-400 hover:text-primary-300">
                the generation view
              </Link>{' '}
              to see detailed progress events.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
