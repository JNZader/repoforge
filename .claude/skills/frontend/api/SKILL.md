---
name: add-api-functions
description: >
  Patterns for integrating the API layer with React Query.
  Trigger: When the api module is imported or used.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [handle-react-query, manage-errors]
load_priority: high
---

<!-- L1:START -->
# add-api-functions

Provides concise patterns for calling backend services via the `api` module.

**Trigger**: When the api module is imported or used.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Fetch data with React Query | `useQuery(['key'], fetchApi)` |
| Start a generation | `startGeneration(params)` |
| Cancel streaming | `cancelGeneration(id)` |

## Critical Patterns (Summary)
- **Query API with `fetchApi`**: Wrap `fetchApi` in `useQuery` for caching and error handling.
- **Stream generation safely**: Use `streamGeneration` with `cancelGeneration` to manage aborts.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Query API with `fetchApi`

Leverage `@tanstack/react-query` to call `fetchApi` and automatically handle loading, caching, and errors.

```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '@/lib/api';

export const useUser = (userId: string) =>
  useQuery(['user', userId], () => fetchApi(`/users/${userId}`), {
    retry: 2,
    onError: (err: ApiError) => console.error(err.message),
  });
```

### Stream generation safely with `streamGeneration` and `cancelGeneration`

Start a streaming generation, subscribe to updates, and provide a cancel button that calls `cancelGeneration`.

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { streamGeneration, cancelGeneration } from '@/lib/api';

export const useGeneration = () => {
  const queryClient = useQueryClient();

  const mutation = useMutation(
    (payload) => streamGeneration(payload),
    {
      onSuccess: (data) => queryClient.setQueryData(['generation', data.id], data),
    }
  );

  const cancel = (id: string) => cancelGeneration(id);
  return { ...mutation, cancel };
};
```

## When to Use

- Fetching any REST endpoint where caching and stale‑while‑revalidate are desired.
- Initiating or cancelling long‑running AI generation streams.
- Displaying analytics data via `fetchAnalyticsSummary` or `fetchAnalyticsUsage`.

## Commands

```bash
# Run the Python CLI entry point
python -m repoforge.cli run

# Build and start the Docker environment
docker compose up --build
```

## Anti-Patterns

### Don't: swallow `ApiError` without handling

Ignoring the structured error loses context and makes debugging hard.

```typescript
// BAD
fetchApi('/bad-endpoint')
  .then(res => res.json())
  .catch(() => {/* silently ignore */});
```
<!-- L3:END -->