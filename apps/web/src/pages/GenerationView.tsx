/** GenerationView — real-time SSE progress, completion preview, download. */

import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  CheckCircle,
  XCircle,
  Loader2,
  Circle,
  AlertTriangle,
  Download,
  RefreshCw,
  ExternalLink,
  Ban,
} from 'lucide-react';
import { useGenerationStream, type StepItem } from '@/hooks/useGenerationStream';
import { useGeneration, useCancelGeneration } from '@/lib/api';
import { cn } from '@/lib/utils';

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

function StepRow({ step }: { step: StepItem }) {
  return (
    <div className="flex items-center gap-3 rounded-md px-3 py-2 text-sm">
      {step.status === 'completed' && <CheckCircle className="h-4 w-4 shrink-0 text-green-400" />}
      {step.status === 'running' && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary-400" />}
      {step.status === 'pending' && <Circle className="h-4 w-4 shrink-0 text-text-muted" />}
      {step.status === 'error' && <XCircle className="h-4 w-4 shrink-0 text-red-400" />}
      <div className="flex-1 min-w-0">
        <span className={cn(
          'truncate',
          step.status === 'completed' ? 'text-text-primary' :
          step.status === 'running' ? 'text-primary-300' :
          step.status === 'error' ? 'text-red-300' :
          'text-text-muted',
        )}>
          {step.label}
        </span>
        {step.detail && (
          <span className="ml-2 text-xs text-text-muted">{step.detail}</span>
        )}
      </div>
      {step.durationMs != null && (
        <span className="text-xs text-text-muted">{formatDuration(step.durationMs)}</span>
      )}
    </div>
  );
}

export function GenerationView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const stream = useGenerationStream(id ?? null);
  const { data: generation } = useGeneration(id);
  const cancelMutation = useCancelGeneration();

  const progressPercent =
    stream.progress.total > 0
      ? Math.round((stream.progress.current / stream.progress.total) * 100)
      : 0;

  const repoName = generation?.repo_url?.replace('https://github.com/', '') ?? id ?? '';

  const handleCancel = () => {
    if (id) {
      cancelMutation.mutate(id);
    }
  };

  const API_URL = import.meta.env.VITE_API_URL ?? '';

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">
          {stream.status === 'completed'
            ? 'Generation Complete'
            : stream.status === 'error'
              ? 'Generation Failed'
              : stream.status === 'cancelled'
                ? 'Generation Cancelled'
                : `Generating: ${repoName}`}
        </h1>
        {generation && (
          <p className="text-sm text-text-secondary">
            Mode: {generation.mode} &middot; Model: {generation.model}
          </p>
        )}
      </div>

      {/* ─── Running State ──────────────────────────── */}
      {(stream.status === 'connecting' || stream.status === 'running' || stream.status === 'idle') && (
        <div className="space-y-4 rounded-lg border border-surface-border bg-surface-card p-5">
          {/* Step list */}
          <div className="max-h-96 space-y-0.5 overflow-auto">
            {stream.steps.length > 0 ? (
              stream.steps.map((step, i) => <StepRow key={i} step={step} />)
            ) : (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
                <span className="ml-3 text-text-secondary">Connecting to stream...</span>
              </div>
            )}
          </div>

          {/* Progress bar */}
          {stream.progress.total > 0 && (
            <div>
              <div className="flex items-center justify-between text-xs text-text-muted mb-1.5">
                <span>{progressPercent}%</span>
                <span>
                  {stream.progress.current}/{stream.progress.total}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-hover">
                <div
                  className="h-full rounded-full bg-primary-500 transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}

          {/* Cancel button */}
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelMutation.isPending}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <Ban className="h-4 w-4" />
            {cancelMutation.isPending ? 'Cancelling...' : 'Cancel'}
          </button>
        </div>
      )}

      {/* ─── Completed State ────────────────────────── */}
      {stream.status === 'completed' && (
        <>
          {/* Success banner */}
          <div className="flex items-center gap-3 rounded-lg border border-green-500/25 bg-green-500/10 px-5 py-4">
            <CheckCircle className="h-6 w-6 text-green-400" />
            <div>
              <p className="font-medium text-green-300">Generation Complete</p>
              <p className="text-sm text-green-400/80">
                {stream.result?.filesGenerated} files generated in{' '}
                {stream.result?.durationMs ? formatDuration(stream.result.durationMs) : '—'}
              </p>
            </div>
          </div>

          {/* Completed steps */}
          <div className="rounded-lg border border-surface-border bg-surface-card p-4">
            <div className="max-h-64 space-y-0.5 overflow-auto">
              {stream.steps.map((step, i) => (
                <StepRow key={i} step={step} />
              ))}
            </div>
          </div>

          {/* Preview iframe */}
          {id && (
            <div className="overflow-hidden rounded-lg border border-surface-border">
              <div className="flex items-center justify-between border-b border-surface-border bg-surface-card px-4 py-2.5">
                <span className="text-sm font-medium text-text-primary">Preview</span>
                <a
                  href={`${API_URL}/api/generate/${id}/preview`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
                >
                  Open in new tab <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              <iframe
                src={`${API_URL}/api/generate/${id}/preview`}
                className="h-[500px] w-full bg-white"
                title="Docsify Preview"
              />
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-wrap gap-3">
            <a
              href={`${API_URL}/api/generate/${id}/download`}
              className="btn-primary flex items-center gap-2"
            >
              <Download className="h-4 w-4" />
              Download ZIP
            </a>
            <button
              type="button"
              onClick={() => navigate('/generate')}
              className="btn-secondary flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Generate Again
            </button>
            <Link to="/history" className="btn-secondary flex items-center gap-2">
              View in History
            </Link>
          </div>
        </>
      )}

      {/* ─── Error State ────────────────────────────── */}
      {stream.status === 'error' && (
        <div className="space-y-4">
          <div className="rounded-lg border border-red-500/25 bg-red-500/10 px-5 py-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-red-400" />
              <div>
                <p className="font-medium text-red-300">Generation Failed</p>
                <p className="text-sm text-red-400/80">{stream.error}</p>
                {stream.errorId && (
                  <p className="mt-1 font-mono text-xs text-red-400/60">
                    Error ID: {stream.errorId}
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => navigate('/generate')}
              className="btn-primary flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* ─── Cancelled State ────────────────────────── */}
      {stream.status === 'cancelled' && (
        <div className="space-y-4">
          <div className="rounded-lg border border-yellow-500/25 bg-yellow-500/10 px-5 py-4">
            <div className="flex items-center gap-3">
              <Ban className="h-6 w-6 text-yellow-400" />
              <div>
                <p className="font-medium text-yellow-300">Generation Cancelled</p>
                <p className="text-sm text-yellow-400/80">
                  The generation was cancelled before completion.
                </p>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => navigate('/generate')}
            className="btn-primary flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Generate Again
          </button>
        </div>
      )}
    </div>
  );
}
