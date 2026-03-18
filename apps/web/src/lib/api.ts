/** Fetch wrapper with auth, 401 handling, and TanStack Query hooks. */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type {
  AnalyticsSummary,
  GenerateRequest,
  GenerateResponse,
  Generation,
  GenerationSSEEvent,
  PaginatedResponse,
  ProviderKey,
  UsageDataPoint,
  ModelUsage,
  RepoUsage,
} from './types';

const API_URL = import.meta.env.VITE_API_URL ?? '';

// ─── Error Class ──────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// ─── Fetch Wrapper ────────────────────────────────────────

export async function fetchApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('repoforge_token');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  // Global 401 handler: clear token and redirect to login
  if (response.status === 401) {
    const currentPath = window.location.hash;
    if (!currentPath.includes('/login') && !currentPath.includes('/auth/callback')) {
      localStorage.removeItem('repoforge_token');
      localStorage.removeItem('repoforge_user');
      window.location.hash = '#/login';
    }
    throw new ApiError(401, 'unauthorized', 'Session expired');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const b = body as { error?: string; message?: string };
    throw new ApiError(response.status, b.error ?? 'unknown', b.message ?? response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ─── SSE Client ───────────────────────────────────────────

export function streamGeneration(
  generationId: string,
  onEvent: (event: GenerationSSEEvent) => void,
  onError?: (error: Error) => void,
): () => void {
  const token = localStorage.getItem('repoforge_token');
  const url = `${API_URL}/api/generate/${generationId}/stream`;

  const eventSource = new EventSource(
    token ? `${url}?token=${encodeURIComponent(token)}` : url,
  );

  const handleMessage = (eventType: string) => (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data as string) as GenerationSSEEvent;
      onEvent({ ...data, type: eventType });
    } catch {
      // ignore parse errors
    }
  };

  const eventTypes = [
    'generation_started',
    'phase_changed',
    'scan_complete',
    'chapter_started',
    'chapter_completed',
    'skill_started',
    'skill_completed',
    'generation_completed',
    'generation_error',
    'generation_cancelled',
  ];

  for (const type of eventTypes) {
    eventSource.addEventListener(type, handleMessage(type));
  }

  eventSource.onerror = () => {
    onError?.(new Error('SSE connection error'));
    eventSource.close();
  };

  return () => eventSource.close();
}

// ─── API Functions ────────────────────────────────────────

export async function startGeneration(data: GenerateRequest): Promise<GenerateResponse> {
  return fetchApi<GenerateResponse>('/api/generate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function cancelGeneration(id: string): Promise<void> {
  return fetchApi<void>(`/api/generate/${id}/cancel`, { method: 'POST' });
}

export async function fetchGeneration(id: string): Promise<Generation> {
  return fetchApi<Generation>(`/api/generate/${id}`);
}

export async function fetchGenerations(params?: {
  page?: number;
  per_page?: number;
  status?: string;
  mode?: string;
  search?: string;
}): Promise<PaginatedResponse<Generation>> {
  const query = new URLSearchParams();
  if (params?.page) query.set('page', String(params.page));
  if (params?.per_page) query.set('per_page', String(params.per_page));
  if (params?.status) query.set('status', params.status);
  if (params?.mode) query.set('mode', params.mode);
  if (params?.search) query.set('search', params.search);
  const qs = query.toString();
  return fetchApi<PaginatedResponse<Generation>>(`/api/history${qs ? `?${qs}` : ''}`);
}

export async function fetchProviders(): Promise<ProviderKey[]> {
  return fetchApi<ProviderKey[]>('/api/providers');
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  return fetchApi<AnalyticsSummary>('/api/analytics/summary');
}

export async function fetchAnalyticsUsage(days = 30): Promise<UsageDataPoint[]> {
  return fetchApi<UsageDataPoint[]>(`/api/analytics/usage?days=${days}`);
}

export async function fetchAnalyticsModels(): Promise<ModelUsage[]> {
  return fetchApi<ModelUsage[]>('/api/analytics/models');
}

export async function fetchAnalyticsRepos(): Promise<RepoUsage[]> {
  return fetchApi<RepoUsage[]>('/api/analytics/repos');
}

// ─── TanStack Query Hooks ─────────────────────────────────

export function useGenerations(params?: { page?: number; per_page?: number; status?: string; mode?: string; search?: string }) {
  return useQuery({
    queryKey: ['generations', params],
    queryFn: () => fetchGenerations(params),
  });
}

export function useGeneration(id: string | undefined) {
  return useQuery({
    queryKey: ['generation', id],
    queryFn: () => fetchGeneration(id!),
    enabled: !!id,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ['providers'],
    queryFn: fetchProviders,
  });
}

export function useAnalyticsSummary() {
  return useQuery({
    queryKey: ['analytics', 'summary'],
    queryFn: fetchAnalyticsSummary,
  });
}

export function useAnalyticsUsage(days = 30) {
  return useQuery({
    queryKey: ['analytics', 'usage', days],
    queryFn: () => fetchAnalyticsUsage(days),
  });
}

export function useAnalyticsModels() {
  return useQuery({
    queryKey: ['analytics', 'models'],
    queryFn: fetchAnalyticsModels,
  });
}

export function useAnalyticsRepos() {
  return useQuery({
    queryKey: ['analytics', 'repos'],
    queryFn: fetchAnalyticsRepos,
  });
}

export function useStartGeneration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startGeneration,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['generations'] });
    },
  });
}

export function useCancelGeneration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelGeneration,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['generations'] });
    },
  });
}

// ─── Provider Mutations ──────────────────────────────────

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { provider: string; key: string; storage?: 'persistent' | 'session' }) =>
      fetchApi<ProviderKey>('/api/providers', {
        method: 'POST',
        body: JSON.stringify({
          provider: data.provider,
          api_key: data.key,
          storage: data.storage ?? 'persistent',
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['providers'] });
    },
  });
}

export function useDeleteProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      fetchApi<void>(`/api/providers/${provider}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['providers'] });
    },
  });
}

export function useDeleteSessionProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      fetchApi<void>(`/api/providers/session/${provider}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['providers'] });
    },
  });
}

export function useValidateProvider() {
  return useMutation({
    mutationFn: (data: { provider: string; key: string }) =>
      fetchApi<{ valid: boolean; error?: string }>('/api/providers/validate', {
        method: 'POST',
        body: JSON.stringify({ provider: data.provider, api_key: data.key }),
      }),
  });
}

export function useDeleteGeneration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      fetchApi<void>(`/api/history/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['generations'] });
    },
  });
}
