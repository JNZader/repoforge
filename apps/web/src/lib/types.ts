/** Core TypeScript types matching the backend API schemas. */

// ─── Auth ─────────────────────────────────────────────────

export interface User {
  github_user_id: number;
  login: string;
  avatar_url: string;
}

// ─── Provider Keys ────────────────────────────────────────

export interface ProviderKey {
  provider: string;
  key_hint: string | null;
  validated_at: string | null;
  status?: string;
  note?: string;
  storage?: 'persistent' | 'session';
}

// ─── Generation ───────────────────────────────────────────

export type GenerationMode = 'docs' | 'skills' | 'both';
export type GenerationStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface GenerateRequest {
  repo_url: string;
  mode: GenerationMode;
  language: string;
  provider: string;
  model: string;
  complexity?: string;
  targets?: string[];
  disclosure?: string;
  theme?: string;
  compress?: boolean;
  hooks?: boolean;
  plugin?: boolean;
}

export interface GenerateResponse {
  generation_id: string;
  status: GenerationStatus;
  created_at: string;
}

export interface Generation {
  id: string;
  user_id: number;
  repo_url: string;
  mode: GenerationMode;
  status: GenerationStatus;
  model: string;
  provider: string;
  language: string;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  files_generated: number | null;
  total_tokens: number | null;
  error_message: string | null;
  error_id: string | null;
  result_metadata: Record<string, unknown> | null;
}

export interface GenerationEvent {
  id: string;
  generation_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

// ─── SSE Events ───────────────────────────────────────────

export interface GenerationSSEEvent {
  type: string;
  [key: string]: unknown;
}

export interface GenerationStartedEvent extends GenerationSSEEvent {
  type: 'generation_started';
  generation_id: string;
  repo_url: string;
  mode: GenerationMode;
}

export interface PhaseChangedEvent extends GenerationSSEEvent {
  type: 'phase_changed';
  phase: 'cloning' | 'scanning' | 'generating' | 'packaging';
}

export interface ScanCompleteEvent extends GenerationSSEEvent {
  type: 'scan_complete';
  layers: number;
  files: number;
  complexity: string;
}

export interface ChapterStartedEvent extends GenerationSSEEvent {
  type: 'chapter_started';
  index: number;
  total: number;
  title: string;
}

export interface ChapterCompletedEvent extends GenerationSSEEvent {
  type: 'chapter_completed';
  index: number;
  total: number;
  title: string;
  tokens: number;
}

export interface SkillStartedEvent extends GenerationSSEEvent {
  type: 'skill_started';
  index: number;
  total: number;
  layer: string;
  module: string;
}

export interface SkillCompletedEvent extends GenerationSSEEvent {
  type: 'skill_completed';
  index: number;
  total: number;
  layer: string;
  module: string;
}

export interface GenerationCompletedEvent extends GenerationSSEEvent {
  type: 'generation_completed';
  generation_id: string;
  duration_ms: number;
  files_generated: number;
}

export interface GenerationErrorEvent extends GenerationSSEEvent {
  type: 'generation_error';
  generation_id: string;
  error: string;
  error_id: string;
}

export interface GenerationCancelledEvent extends GenerationSSEEvent {
  type: 'generation_cancelled';
  generation_id: string;
}

// ─── Analytics ────────────────────────────────────────────

export interface AnalyticsSummary {
  total_generations: number;
  successful_generations: number;
  failed_generations: number;
  success_rate: number;
  avg_duration_ms: number;
  total_tokens: number;
}

export interface UsageDataPoint {
  date: string;
  count: number;
}

export interface ModelUsage {
  model: string;
  count: number;
  avg_duration_ms: number;
}

export interface RepoUsage {
  repo_url: string;
  count: number;
  last_generated: string;
}

// ─── Paginated Response ───────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}
