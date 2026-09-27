---
name: manage-api
description: >
  Provides patterns for robust API interaction in the frontend.
  Trigger: load when any `api` function or hook is imported.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills: [handle-errors, use-react-query]
load_priority: high
---

<!-- L1:START -->
# manage-api

Provides patterns for robust API interaction in the frontend.

**Trigger**: load when any `api` function or hook is imported.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| fetch a single generation | `useGeneration(id)` |
| start a new generation | `useStartGeneration()` |
| cancel a generation | `useCancelGeneration()` |

## Critical Patterns (Summary)
- **Consistent error handling with `ApiError`**: wrap `fetchApi` calls and inspect `instanceof ApiError`.
- **React Query hooks for generation lifecycle**: use `useGeneration`, `useStartGeneration`, and `useCancelGeneration` to keep UI in sync.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Consistent error handling with `ApiError`

Catch `ApiError` from `fetchApi` to surface HTTP status and custom codes instead of generic errors.

```typescript
import { fetchApi, ApiError } from './api';

async function loadProviders() {
  try {
    const providers = await fetchApi<ProviderKey[]>('/api/providers');
    return providers;
  } catch (err) {
    if (err instanceof ApiError) {
      console.error(`API ${err.status} – ${err.code}: ${err.message}`);
    } else {
      console.error('Unexpected error', err);
    }
    throw err;
  }
}
```

### React Query hooks for generation lifecycle

Leverage the provided hooks to fetch, start, and cancel generations while automatically invalidating related queries.

```typescript
import { useGeneration, useStartGeneration, useCancelGeneration } from './api';

// Fetch a generation by ID
function GenerationDetail({ id }: { id: string }) {
  const { data, isLoading, error } = useGeneration(id);
  if (isLoading) return <p>Loading…</p>;
  if (error) return <p>Error loading generation.</p>;
  return <pre>{JSON.stringify(data, null, 2)}</pre>;
}

// Start a new generation
function NewGenerationButton({ request }: { request: GenerateRequest }) {
  const { mutateAsync, isLoading } = useStartGeneration();
  const handleClick = async () => {
    await mutateAsync(request);
  };
  return <button onClick={handleClick} disabled={isLoading}>Generate</button>;
}

// Cancel an ongoing generation
function CancelButton({ id }: { id: string }) {
  const { mutateAsync } = useCancelGeneration();
  return <button onClick={() => mutateAsync(id)}>Cancel</button>;
}
```

## When to Use

- When you need to call any `/api/*` endpoint from the React frontend.
- When you want automatic cache invalidation after starting or cancelling a generation.
- When you must surface detailed server errors to the UI.

## Commands

```bash
# Build and run the Docker environment
docker compose up --build

# Execute the CLI entry point inside the container
docker exec -it app