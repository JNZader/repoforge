---
name: add-api-integration
description: >
  Centralized API integration patterns for generation, analytics, and provider management.
  Trigger: when integrating with the api layer or building generation workflows.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: medium
token_estimate: 600
dependencies: []
related_skills: []
load_priority: high
---

<!-- L1:START -->
# add-api-integration

One sentence: Centralized API integration patterns for generation, analytics, and provider management.

**Trigger**: when building generation workflows or integrating with the api layer.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Fetch generations | `useGenerations()` |
| Start generation | `useStartGeneration()` |
| Manage providers | `useProviders()` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: Fetch Generations with Query Keys

Use `fetchGenerations` with typed params and `useGenerations` hook for server-driven state.

```typescript
import { fetchGenerations, useGenerations } from '@/lib/api';

// Fetch with pagination params
const { data, isLoading } = await fetchGenerations({
  page: 1,
  per_page: 10,
  status: 'completed',
});

// Hook-based usage
const { data: generations, isPending } = useGenerations({
  page: 1,
  search: 'ai',
});
```

### Pattern 2: Start Generation and Invalidate Cache

Use `startGeneration` with `useMutation` to trigger generation and auto-invalidate queries.

```typescript
import { useStartGeneration, useGenerations } from '@/lib/api';

const { mutate: startGen, isPending } = useStartGeneration();
const { refetch } = useGenerations();

await startGen({ provider: 'openai', model: 'gpt-4' });
// Cache automatically refreshed via onSuccess
await refetch();
```

## When to Use

- Building new generation workflows in the frontend
- Fetching generation history with filters (status, mode, search)
- Managing provider configurations and keys

## Commands

```bash
# Development: start the web app with API mocking
docker compose -f docker-compose.dev.yml up web

# Run type checks on API layer
npx tsc --noEmit apps/web/src/lib/api.ts
```

## Anti-Patterns

### Don't: Ignore ApiError status codes

Accessing response data without checking `status` leads to runtime crashes when the API returns 4xx/5xx.

```typescript
// BAD — assumes success even on error
const result = await fetchApi('/api/generate'); // crashes if status >= 400

// GOOD — check status first
const result = await fetchApi('/api/generate');
if (result.status >= 400) throw new ApiError(result.status, result.code, result.message);
```
<!-- L3:END -->