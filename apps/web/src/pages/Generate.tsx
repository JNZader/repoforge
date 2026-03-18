/** Generate page — the main feature: form to configure and start generation. */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useStartGeneration, useProviders } from '@/lib/api';
import type { GenerationMode } from '@/lib/types';
import { cn } from '@/lib/utils';

const LANGUAGES = [
  'english', 'spanish', 'french', 'german', 'portuguese', 'italian',
  'japanese', 'korean', 'chinese', 'russian', 'arabic',
] as const;

const MODEL_PRESETS = [
  { label: 'Claude 3.5 Haiku', value: 'claude-3-5-haiku-20241022' },
  { label: 'Claude Sonnet 4', value: 'claude-sonnet-4-20250514' },
  { label: 'GPT-4o Mini', value: 'gpt-4o-mini' },
  { label: 'GPT-4.1 Mini', value: 'gpt-4.1-mini' },
  { label: 'Gemini 2.0 Flash', value: 'gemini-2.0-flash' },
] as const;

const TARGETS = ['claude', 'opencode', 'cursor', 'codex', 'gemini', 'copilot', 'windsurf'] as const;

const GITHUB_URL_REGEX = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/;

export function Generate() {
  const navigate = useNavigate();
  const mutation = useStartGeneration();
  const { data: providers } = useProviders();

  // Form state
  const [repoUrl, setRepoUrl] = useState('');
  const [mode, setMode] = useState<GenerationMode>('docs');
  const [language, setLanguage] = useState('english');
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('claude-3-5-haiku-20241022');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Advanced options
  const [complexity, setComplexity] = useState('auto');
  const [selectedTargets, setSelectedTargets] = useState<string[]>(['claude']);
  const [disclosure, setDisclosure] = useState('tiered');
  const [theme, setTheme] = useState('vue');
  const [compress, setCompress] = useState(false);
  const [hooks, setHooks] = useState(true);
  const [plugin, setPlugin] = useState(false);

  const [errors, setErrors] = useState<string[]>([]);

  const validate = (): string[] => {
    const errs: string[] = [];
    if (!repoUrl.trim()) {
      errs.push('GitHub repository URL is required.');
    } else if (!GITHUB_URL_REGEX.test(repoUrl.trim())) {
      errs.push('Please enter a valid GitHub repository URL (https://github.com/owner/repo).');
    }
    if (!provider && providers && providers.length === 0) {
      errs.push('No API providers configured. Add one in Settings first.');
    }
    return errs;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validationErrors = validate();
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }
    setErrors([]);

    mutation.mutate(
      {
        repo_url: repoUrl.trim(),
        mode,
        language,
        provider: provider || (providers?.[0]?.provider ?? 'github-models'),
        model,
        complexity: complexity === 'auto' ? undefined : complexity,
        targets: mode !== 'docs' ? selectedTargets : undefined,
        disclosure,
        theme: mode !== 'skills' ? theme : undefined,
        compress,
        hooks,
        plugin,
      },
      {
        onSuccess: (resp) => {
          navigate(`/generate/${resp.generation_id}`);
        },
        onError: (err) => {
          setErrors([(err as Error).message || 'Failed to start generation.']);
        },
      },
    );
  };

  const toggleTarget = (target: string) => {
    setSelectedTargets((prev) =>
      prev.includes(target) ? prev.filter((t) => t !== target) : [...prev, target],
    );
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Generate Documentation & Skills</h1>
        <p className="text-sm text-text-secondary">
          Paste a GitHub URL, configure options, and generate production-ready documentation.
        </p>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="rounded-lg border border-red-500/25 bg-red-500/10 p-4">
          {errors.map((err, i) => (
            <p key={i} className="flex items-center gap-2 text-sm text-red-400">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {err}
            </p>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Repo URL */}
        <div>
          <label htmlFor="repo-url" className="mb-2 block text-sm font-medium text-text-primary">
            GitHub Repository URL
          </label>
          <input
            id="repo-url"
            type="url"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/user/repo"
            className="input-field"
            required
          />
        </div>

        {/* Mode selector */}
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-text-primary">What to generate</legend>
          <div className="flex gap-3">
            {(['docs', 'skills', 'both'] as const).map((m) => (
              <label
                key={m}
                className={cn(
                  'flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-all',
                  mode === m
                    ? 'border-primary-500 bg-primary-600/15 text-primary-400'
                    : 'border-surface-border bg-surface-card text-text-secondary hover:border-surface-hover',
                )}
              >
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => setMode(m)}
                  className="sr-only"
                />
                {m === 'docs' ? 'Docs' : m === 'skills' ? 'Skills' : 'Both'}
              </label>
            ))}
          </div>
        </fieldset>

        {/* Language + Provider row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="language" className="mb-2 block text-sm font-medium text-text-primary">
              Language
            </label>
            <select
              id="language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="select-field"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang.charAt(0).toUpperCase() + lang.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="provider" className="mb-2 block text-sm font-medium text-text-primary">
              Provider
            </label>
            <select
              id="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="select-field"
            >
              <option value="">Auto (first available)</option>
              {providers?.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.provider} {p.key_hint ? `(${p.key_hint})` : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Model */}
        <div>
          <label htmlFor="model" className="mb-2 block text-sm font-medium text-text-primary">
            Model
          </label>
          <div className="flex gap-2">
            <input
              id="model"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="claude-3-5-haiku-20241022"
              className="input-field flex-1"
            />
            <select
              value=""
              onChange={(e) => {
                if (e.target.value) setModel(e.target.value);
              }}
              className="select-field w-auto"
              aria-label="Model presets"
            >
              <option value="">Presets</option>
              {MODEL_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Advanced Options */}
        <div className="rounded-lg border border-surface-border bg-surface-card">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
          >
            {showAdvanced ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            Advanced Options
          </button>

          {showAdvanced && (
            <div className="border-t border-surface-border px-4 pb-4 pt-3 space-y-4">
              {/* Complexity */}
              <div>
                <label htmlFor="complexity" className="mb-1 block text-sm text-text-secondary">
                  Complexity
                </label>
                <select
                  id="complexity"
                  value={complexity}
                  onChange={(e) => setComplexity(e.target.value)}
                  className="select-field"
                >
                  <option value="auto">Auto-detect</option>
                  <option value="simple">Simple</option>
                  <option value="medium">Medium</option>
                  <option value="complex">Complex</option>
                </select>
              </div>

              {/* Targets (for skills mode) */}
              {mode !== 'docs' && (
                <div>
                  <p className="mb-2 text-sm text-text-secondary">Targets</p>
                  <div className="flex flex-wrap gap-2">
                    {TARGETS.map((target) => (
                      <button
                        key={target}
                        type="button"
                        onClick={() => toggleTarget(target)}
                        className={cn(
                          'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                          selectedTargets.includes(target)
                            ? 'bg-primary-600/20 text-primary-400 ring-1 ring-primary-500/50'
                            : 'bg-surface-hover text-text-muted hover:text-text-secondary',
                        )}
                      >
                        {target}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Disclosure + Theme row */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="disclosure" className="mb-1 block text-sm text-text-secondary">
                    Disclosure
                  </label>
                  <select
                    id="disclosure"
                    value={disclosure}
                    onChange={(e) => setDisclosure(e.target.value)}
                    className="select-field"
                  >
                    <option value="tiered">Tiered</option>
                    <option value="full">Full</option>
                    <option value="minimal">Minimal</option>
                  </select>
                </div>
                {mode !== 'skills' && (
                  <div>
                    <label htmlFor="theme" className="mb-1 block text-sm text-text-secondary">
                      Docsify Theme
                    </label>
                    <select
                      id="theme"
                      value={theme}
                      onChange={(e) => setTheme(e.target.value)}
                      className="select-field"
                    >
                      <option value="vue">Vue</option>
                      <option value="dark">Dark</option>
                      <option value="buble">Buble</option>
                      <option value="pure">Pure</option>
                    </select>
                  </div>
                )}
              </div>

              {/* Toggles row */}
              <div className="flex flex-wrap gap-6">
                <label className="flex items-center gap-2 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={compress}
                    onChange={(e) => setCompress(e.target.checked)}
                    className="h-4 w-4 rounded border-surface-border text-primary-600"
                  />
                  Compress output
                </label>
                <label className="flex items-center gap-2 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={hooks}
                    onChange={(e) => setHooks(e.target.checked)}
                    className="h-4 w-4 rounded border-surface-border text-primary-600"
                  />
                  Include hooks
                </label>
                <label className="flex items-center gap-2 text-sm text-text-secondary">
                  <input
                    type="checkbox"
                    checked={plugin}
                    onChange={(e) => setPlugin(e.target.checked)}
                    className="h-4 w-4 rounded border-surface-border text-primary-600"
                  />
                  Include plugin
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={mutation.isPending || !repoUrl.trim()}
          className={cn(
            'flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-medium text-white transition-all',
            mutation.isPending || !repoUrl.trim()
              ? 'cursor-not-allowed bg-primary-600/50 opacity-60'
              : 'bg-gradient-to-r from-primary-600 to-primary-700 shadow-md hover:from-primary-700 hover:to-primary-800 hover:shadow-lg',
          )}
        >
          {mutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          {mutation.isPending ? 'Starting...' : 'Generate Documentation'}
        </button>
      </form>
    </div>
  );
}
