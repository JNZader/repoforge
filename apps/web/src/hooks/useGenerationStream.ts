/** Custom hook wrapping EventSource for real-time generation progress. */

import { useState, useEffect, useRef, useCallback } from 'react';
import { streamGeneration } from '@/lib/api';
import type { GenerationSSEEvent } from '@/lib/types';

export type StreamStatus = 'idle' | 'connecting' | 'running' | 'completed' | 'error' | 'cancelled';

export interface StepItem {
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  detail?: string;
  durationMs?: number;
}

export interface StreamState {
  status: StreamStatus;
  events: GenerationSSEEvent[];
  steps: StepItem[];
  progress: { current: number; total: number };
  error: string | null;
  errorId: string | null;
  result: {
    durationMs: number;
    filesGenerated: number;
  } | null;
}

const TERMINAL_STATUSES = new Set(['completed', 'error', 'cancelled']);

export function useGenerationStream(generationId: string | null): StreamState {
  const [events, setEvents] = useState<GenerationSSEEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [steps, setSteps] = useState<StepItem[]>([]);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);
  const [result, setResult] = useState<StreamState['result']>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const stepTimers = useRef<Map<string, number>>(new Map());

  const addEvent = useCallback((event: GenerationSSEEvent) => {
    setEvents((prev) => [...prev, event]);
  }, []);

  useEffect(() => {
    if (!generationId) return;

    setStatus('connecting');
    setEvents([]);
    setSteps([]);
    setProgress({ current: 0, total: 0 });
    setError(null);
    setErrorId(null);
    setResult(null);
    stepTimers.current.clear();

    const cleanup = streamGeneration(
      generationId,
      (event: GenerationSSEEvent) => {
        addEvent(event);

        switch (event.type) {
          case 'generation_started': {
            setStatus('running');
            setSteps([
              { label: 'Cloning repository...', status: 'pending' },
              { label: 'Scanning codebase...', status: 'pending' },
            ]);
            break;
          }

          case 'phase_changed': {
            const phase = event.phase as string;
            if (phase === 'cloning') {
              stepTimers.current.set('cloning', Date.now());
              setSteps((prev) =>
                prev.map((s, i) => (i === 0 ? { ...s, status: 'running' as const } : s)),
              );
            } else if (phase === 'scanning') {
              const cloneStart = stepTimers.current.get('cloning');
              const cloneDuration = cloneStart ? Date.now() - cloneStart : undefined;
              stepTimers.current.set('scanning', Date.now());
              setSteps((prev) =>
                prev.map((s, i) => {
                  if (i === 0) return { ...s, status: 'completed' as const, durationMs: cloneDuration };
                  if (i === 1) return { ...s, status: 'running' as const };
                  return s;
                }),
              );
            } else if (phase === 'generating') {
              const scanStart = stepTimers.current.get('scanning');
              const scanDuration = scanStart ? Date.now() - scanStart : undefined;
              setSteps((prev) =>
                prev.map((s, i) => {
                  if (i === 1) return { ...s, status: 'completed' as const, durationMs: scanDuration };
                  return s;
                }),
              );
            }
            break;
          }

          case 'scan_complete': {
            const layers = event.layers as number;
            const files = event.files as number;
            const complexity = event.complexity as string;
            setSteps((prev) =>
              prev.map((s, i) => {
                if (i === 1) {
                  return {
                    ...s,
                    detail: `${layers} layers, ${files} files, ${complexity} complexity`,
                  };
                }
                return s;
              }),
            );
            break;
          }

          case 'chapter_started': {
            const index = event.index as number;
            const total = event.total as number;
            const title = event.title as string;
            stepTimers.current.set(`chapter-${index}`, Date.now());
            setProgress({ current: index - 1, total });
            setSteps((prev) => {
              const existing = prev.find((s) => s.label === `[${index}/${total}] ${title}`);
              if (existing) {
                return prev.map((s) =>
                  s.label === existing.label ? { ...s, status: 'running' as const } : s,
                );
              }
              // Add pending steps for all chapters if not yet added
              const newSteps = [...prev];
              for (let i = index; i <= total; i++) {
                const chTitle = i === index ? title : `Chapter ${i}`;
                const label = `[${i}/${total}] ${chTitle}`;
                if (!newSteps.find((s) => s.label === label)) {
                  newSteps.push({
                    label,
                    status: i === index ? 'running' : 'pending',
                  });
                }
              }
              return newSteps;
            });
            break;
          }

          case 'chapter_completed': {
            const index = event.index as number;
            const total = event.total as number;
            const title = event.title as string;
            const tokens = event.tokens as number;
            const startTime = stepTimers.current.get(`chapter-${index}`);
            const duration = startTime ? Date.now() - startTime : undefined;
            setProgress({ current: index, total });
            setSteps((prev) =>
              prev.map((s) => {
                const label = `[${index}/${total}] ${title}`;
                if (s.label === label) {
                  return {
                    ...s,
                    status: 'completed' as const,
                    detail: `${tokens} tokens`,
                    durationMs: duration,
                  };
                }
                return s;
              }),
            );
            break;
          }

          case 'skill_started': {
            const index = event.index as number;
            const total = event.total as number;
            const layer = event.layer as string;
            const module = event.module as string;
            stepTimers.current.set(`skill-${index}`, Date.now());
            setProgress({ current: index - 1, total });
            setSteps((prev) => {
              const label = `[${index}/${total}] ${layer}/${module}`;
              if (!prev.find((s) => s.label === label)) {
                return [...prev, { label, status: 'running' as const }];
              }
              return prev.map((s) =>
                s.label === label ? { ...s, status: 'running' as const } : s,
              );
            });
            break;
          }

          case 'skill_completed': {
            const index = event.index as number;
            const total = event.total as number;
            const layer = event.layer as string;
            const module = event.module as string;
            const startTime = stepTimers.current.get(`skill-${index}`);
            const duration = startTime ? Date.now() - startTime : undefined;
            setProgress({ current: index, total });
            setSteps((prev) =>
              prev.map((s) => {
                const label = `[${index}/${total}] ${layer}/${module}`;
                if (s.label === label) {
                  return { ...s, status: 'completed' as const, durationMs: duration };
                }
                return s;
              }),
            );
            break;
          }

          case 'generation_completed': {
            setStatus('completed');
            setResult({
              durationMs: event.duration_ms as number,
              filesGenerated: event.files_generated as number,
            });
            break;
          }

          case 'generation_error': {
            setStatus('error');
            setError(event.error as string);
            setErrorId(event.error_id as string);
            break;
          }

          case 'generation_cancelled': {
            setStatus('cancelled');
            break;
          }
        }
      },
      () => {
        if (!TERMINAL_STATUSES.has(status)) {
          setStatus('error');
          setError('Lost connection to event stream');
        }
      },
    );

    cleanupRef.current = cleanup;
    return () => cleanup();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generationId]);

  return { status, events, steps, progress, error, errorId, result };
}
