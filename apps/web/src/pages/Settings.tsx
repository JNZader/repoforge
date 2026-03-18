/** Settings — provider key management: list, add, validate, delete. */

import { useState } from 'react';
import {
  Settings as SettingsIcon,
  Key,
  Plus,
  Trash2,
  CheckCircle,
  Loader2,
  Shield,
  Eye,
  EyeOff,
  AlertTriangle,
} from 'lucide-react';
import {
  useProviders,
  useCreateProvider,
  useDeleteProvider,
  useDeleteSessionProvider,
  useValidateProvider,
} from '@/lib/api';
import { cn } from '@/lib/utils';

const PROVIDERS = [
  { id: 'anthropic', name: 'Anthropic', prefix: 'sk-ant-' },
  { id: 'openai', name: 'OpenAI', prefix: 'sk-' },
  { id: 'google', name: 'Google', prefix: 'AI' },
  { id: 'groq', name: 'Groq', prefix: 'gsk_' },
  { id: 'mistral', name: 'Mistral', prefix: '' },
  { id: 'github-models', name: 'GitHub Models', prefix: 'ghp_' },
] as const;

export function Settings() {
  const { data: providers, isLoading } = useProviders();
  const createMutation = useCreateProvider();
  const deleteMutation = useDeleteProvider();
  const deleteSessionMutation = useDeleteSessionProvider();
  const validateMutation = useValidateProvider();

  const [showAddForm, setShowAddForm] = useState(false);
  const [newProvider, setNewProvider] = useState('anthropic');
  const [newKey, setNewKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [storageMode, setStorageMode] = useState<'persistent' | 'session'>('persistent');

  const handleAdd = () => {
    if (!newKey.trim()) return;
    setAddError(null);

    createMutation.mutate(
      { provider: newProvider, key: newKey.trim(), storage: storageMode },
      {
        onSuccess: () => {
          setNewKey('');
          setShowAddForm(false);
          setStorageMode('persistent');
          validateMutation.reset();
        },
        onError: (err) => {
          setAddError((err as Error).message || 'Failed to add provider key.');
        },
      },
    );
  };

  const handleValidate = () => {
    if (!newKey.trim()) return;
    setAddError(null);

    validateMutation.mutate(
      { provider: newProvider, key: newKey.trim() },
      {
        onSuccess: (result) => {
          if (!result.valid) {
            setAddError(result.error || 'Key validation failed. Check your API key.');
          }
        },
        onError: (err) => {
          setAddError((err as Error).message || 'Validation failed.');
        },
      },
    );
  };

  const handleDelete = (provider: string) => {
    const saved = providers?.find((pk) => pk.provider === provider);
    const isSession = saved?.storage === 'session';

    if (isSession) {
      deleteSessionMutation.mutate(provider, {
        onSuccess: () => setDeleteConfirm(null),
      });
    } else {
      deleteMutation.mutate(provider, {
        onSuccess: () => setDeleteConfirm(null),
      });
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="h-6 w-6 text-primary-400" />
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
          <p className="text-sm text-text-secondary">
            Manage your LLM provider API keys
          </p>
        </div>
      </div>

      {/* Provider Keys */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5 text-text-secondary" />
            <h2 className="text-lg font-semibold text-text-primary">Provider API Keys</h2>
          </div>
          {!showAddForm && (
            <button
              type="button"
              onClick={() => setShowAddForm(true)}
              className="btn-primary flex items-center gap-1.5 text-sm"
            >
              <Plus className="h-4 w-4" />
              Add Key
            </button>
          )}
        </div>

        {/* Existing keys list */}
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
          </div>
        ) : (
          <div className="space-y-2">
            {PROVIDERS.map((p) => {
              const saved = providers?.find((pk) => pk.provider === p.id);
              const isOAuth = 'oauth' in p && p.oauth;
              const isSession = saved?.storage === 'session';
              const isDeleting = deleteMutation.isPending || deleteSessionMutation.isPending;

              return (
                <div
                  key={p.id}
                  className="flex items-center justify-between rounded-lg border border-surface-border bg-surface-card px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'flex h-9 w-9 items-center justify-center rounded-lg text-xs font-bold',
                        saved || isOAuth
                          ? 'bg-green-500/10 text-green-400'
                          : 'bg-surface-hover text-text-muted',
                      )}
                    >
                      {p.name.charAt(0)}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-text-primary">{p.name}</p>
                      {isOAuth ? (
                        <p className="text-xs text-green-400">Uses your OAuth token</p>
                      ) : saved ? (
                        <div>
                          <p className="text-xs text-text-secondary">
                            {saved.key_hint ?? '****'}
                            {saved.validated_at && (
                              <span className="text-green-400">
                                {' '}
                                · Validated {new Date(saved.validated_at).toLocaleDateString()}
                              </span>
                            )}
                          </p>
                          {isSession && (
                            <p className="mt-0.5 text-xs text-yellow-400">
                              <AlertTriangle className="mr-1 inline h-3 w-3" />
                              Session key — lost on logout or server restart
                            </p>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-text-muted">Not configured</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {isOAuth && (
                      <span className="flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-400">
                        <Shield className="h-3 w-3" />
                        Available
                      </span>
                    )}
                    {saved && !isOAuth && (
                      <>
                        {isSession ? (
                          <span className="rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs font-medium text-yellow-400">
                            Session
                          </span>
                        ) : saved.validated_at ? (
                          <span className="flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-400">
                            <CheckCircle className="h-3 w-3" />
                            Validated
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs font-medium text-yellow-400">
                            <AlertTriangle className="h-3 w-3" />
                            Not validated
                          </span>
                        )}
                        {deleteConfirm === p.id ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-red-400">Delete?</span>
                            <button
                              type="button"
                              onClick={() => handleDelete(p.id)}
                              disabled={isDeleting}
                              className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50"
                            >
                              {isDeleting ? '...' : 'Yes'}
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteConfirm(null)}
                              className="btn-secondary px-2 py-1 text-xs"
                            >
                              No
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setDeleteConfirm(p.id)}
                            className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-red-500/10 hover:text-red-400"
                            title="Delete key"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Add key form */}
        {showAddForm && (
          <div className="rounded-lg border border-primary-500/25 bg-primary-600/5 p-4">
            <h3 className="mb-3 text-sm font-medium text-text-primary">Add Provider Key</h3>

            <div className="space-y-3">
              {/* Provider select */}
              <div>
                <label htmlFor="add-provider" className="mb-1 block text-xs font-medium text-text-secondary">
                  Provider
                </label>
                <select
                  id="add-provider"
                  value={newProvider}
                  onChange={(e) => setNewProvider(e.target.value)}
                  className="select-field"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* API Key input */}
              <div>
                <label htmlFor="add-key" className="mb-1 block text-xs font-medium text-text-secondary">
                  API Key
                </label>
                <div className="relative">
                  <input
                    id="add-key"
                    type={showKey ? 'text' : 'password'}
                    value={newKey}
                    onChange={(e) => {
                      setNewKey(e.target.value);
                      setAddError(null);
                    }}
                    placeholder="sk-ant-..."
                    className="input-field pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
                  >
                    {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Storage mode */}
              <div>
                <label className="mb-1 block text-xs font-medium text-text-secondary">Storage</label>
                <div className="flex gap-4">
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="radio"
                      name="storageMode"
                      value="persistent"
                      checked={storageMode === 'persistent'}
                      onChange={() => setStorageMode('persistent')}
                      className="accent-primary-600"
                    />
                    <span className="text-sm text-text-primary">Save permanently</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="radio"
                      name="storageMode"
                      value="session"
                      checked={storageMode === 'session'}
                      onChange={() => setStorageMode('session')}
                      className="accent-yellow-500"
                    />
                    <span className="text-sm text-text-primary">Session only</span>
                  </label>
                </div>
                {storageMode === 'session' && (
                  <p className="mt-1 text-xs text-yellow-400">
                    <AlertTriangle className="mr-1 inline h-3 w-3" />
                    This key will only be stored in server memory. Lost on logout or server restart.
                  </p>
                )}
              </div>

              {/* Error display */}
              {addError && (
                <div className="flex items-center gap-2 text-sm text-red-400">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  {addError}
                </div>
              )}

              {/* Validation success */}
              {validateMutation.isSuccess && validateMutation.data.valid && (
                <div className="flex items-center gap-2 text-sm text-green-400">
                  <CheckCircle className="h-4 w-4" />
                  Key is valid!
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleValidate}
                  disabled={!newKey.trim() || validateMutation.isPending}
                  className="btn-secondary flex items-center gap-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {validateMutation.isPending && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  Validate
                </button>
                <button
                  type="button"
                  onClick={handleAdd}
                  disabled={!newKey.trim() || createMutation.isPending}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                    storageMode === 'session'
                      ? 'bg-yellow-600 hover:bg-yellow-700'
                      : 'bg-primary-600 hover:bg-primary-700',
                  )}
                >
                  {createMutation.isPending && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  )}
                  {storageMode === 'session' ? 'Use for Session' : 'Save Key'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false);
                    setNewKey('');
                    setAddError(null);
                    setStorageMode('persistent');
                    validateMutation.reset();
                  }}
                  className="btn-secondary text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
