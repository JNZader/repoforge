/** Analytics — summary stats, usage chart, model breakdown, top repos. */

import { useState } from 'react';
import {
  BarChart3,
  Sparkles,
  TrendingUp,
  Clock,
  Coins,
  Loader2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from 'recharts';
import {
  useAnalyticsSummary,
  useAnalyticsUsage,
  useAnalyticsModels,
  useAnalyticsRepos,
} from '@/lib/api';

const BAR_COLORS = ['#a78bfa', '#7c3aed', '#6d28d9', '#5b21b6', '#4c1d95', '#8b5cf6'];

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

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-card p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-text-secondary">{label}</p>
        <div className="text-primary-400">{icon}</div>
      </div>
      <p className="mt-2 text-2xl font-bold text-text-primary">{value}</p>
    </div>
  );
}

export function Analytics() {
  const [days, setDays] = useState(30);
  const { data: summary, isLoading: summaryLoading } = useAnalyticsSummary();
  const { data: usage, isLoading: usageLoading } = useAnalyticsUsage(days);
  const { data: models, isLoading: modelsLoading } = useAnalyticsModels();
  const { data: repos, isLoading: reposLoading } = useAnalyticsRepos();

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <BarChart3 className="h-6 w-6 text-primary-400" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Analytics</h1>
          <p className="text-sm text-text-secondary">
            Usage statistics and generation insights
          </p>
        </div>
      </div>

      {/* Summary Cards */}
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

      {/* Usage Over Time Chart */}
      <div className="rounded-lg border border-surface-border bg-surface-card">
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-4">
          <h2 className="font-semibold text-text-primary">Usage Over Time</h2>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="select-field w-auto text-sm"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
          </select>
        </div>
        <div className="px-5 py-4">
          {usageLoading ? (
            <div className="flex h-72 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
            </div>
          ) : usage && usage.length > 0 ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={usage} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                  <defs>
                    <linearGradient id="colorGen" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
                  <XAxis
                    dataKey="date"
                    stroke="#8b949e"
                    tick={{ fill: '#8b949e', fontSize: 12 }}
                    tickFormatter={(value: string) => {
                      const d = new Date(value);
                      return `${d.getMonth() + 1}/${d.getDate()}`;
                    }}
                  />
                  <YAxis
                    stroke="#8b949e"
                    tick={{ fill: '#8b949e', fontSize: 12 }}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#161b22',
                      border: '1px solid #30363d',
                      borderRadius: '8px',
                      color: '#e6edf3',
                    }}
                    labelFormatter={(label: string) =>
                      new Date(label).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })
                    }
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="count"
                    name="Generations"
                    stroke="#22c55e"
                    fillOpacity={1}
                    fill="url(#colorGen)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex h-72 items-center justify-center">
              <p className="text-sm text-text-muted">No usage data for this period.</p>
            </div>
          )}
        </div>
      </div>

      {/* Model Breakdown + Top Repos */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Model Usage */}
        <div className="rounded-lg border border-surface-border bg-surface-card">
          <div className="border-b border-surface-border px-5 py-4">
            <h2 className="font-semibold text-text-primary">Model Usage</h2>
          </div>
          <div className="px-5 py-4">
            {modelsLoading ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
              </div>
            ) : models && models.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={models}
                    layout="vertical"
                    margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" horizontal={false} />
                    <XAxis
                      type="number"
                      stroke="#8b949e"
                      tick={{ fill: '#8b949e', fontSize: 12 }}
                      allowDecimals={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="model"
                      stroke="#8b949e"
                      tick={{ fill: '#8b949e', fontSize: 11 }}
                      width={130}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#161b22',
                        border: '1px solid #30363d',
                        borderRadius: '8px',
                        color: '#e6edf3',
                      }}
                      formatter={(value: number, _name: string, props) => {
                        const payload = (props as { payload?: { avg_duration_ms?: number } }).payload;
                        const avgDur = payload?.avg_duration_ms;
                        return [
                          `${value} generations${avgDur ? ` (avg ${formatDuration(avgDur)})` : ''}`,
                          'Usage',
                        ];
                      }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={30}>
                      {models.map((_entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={BAR_COLORS[index % BAR_COLORS.length]}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center">
                <p className="text-sm text-text-muted">No model data yet.</p>
              </div>
            )}
          </div>
        </div>

        {/* Top Repos */}
        <div className="rounded-lg border border-surface-border bg-surface-card">
          <div className="border-b border-surface-border px-5 py-4">
            <h2 className="font-semibold text-text-primary">Top Repositories</h2>
          </div>
          <div className="px-5 py-4">
            {reposLoading ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
              </div>
            ) : repos && repos.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-border text-left">
                      <th className="pb-2 pr-4 font-medium text-text-secondary">Repository</th>
                      <th className="pb-2 pr-4 font-medium text-text-secondary">Count</th>
                      <th className="pb-2 font-medium text-text-secondary">Last Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {repos.map((repo) => {
                      const name = repo.repo_url.replace('https://github.com/', '');
                      return (
                        <tr key={repo.repo_url} className="border-b border-surface-border/50">
                          <td className="py-2.5 pr-4">
                            <a
                              href={repo.repo_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-primary-400 hover:text-primary-300"
                            >
                              {name}
                            </a>
                          </td>
                          <td className="py-2.5 pr-4 text-text-primary">{repo.count}</td>
                          <td className="py-2.5 text-text-secondary">
                            {new Date(repo.last_generated).toLocaleDateString()}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center">
                <p className="text-sm text-text-muted">No repository data yet.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
