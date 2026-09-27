---
name: add-api-client
description: >
  Provides patterns for robust API interaction in the web frontend.
  Trigger: when working with the `api` utilities.
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
# add-api-client

Provides concise patterns for using the API layer in the web app.

**Trigger**: when working with the `api` utilities.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Fetch a generation | `fetchGeneration(id)` |
| Start a generation | `useStartGeneration()` |
| Handle API errors | `throw new ApiError(...)` |

## Critical Patterns (Summary)
- **Error handling with `ApiError`**: Throw and catch typed errors for HTTP failures.
- **React Query hooks**: Use provided `use*` hooks to keep UI in sync with API state.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Error handling with `ApiError`

Wrap `fetchApi` calls in try/catch and re‑throw `ApiError` to expose status and code to UI components.

```typescript
import { fetchApi, ApiError } from './api';

async function loadProviders() {
  try {
    return await fetchApi<ProviderKey[]>('/api/providers');
  } catch (e) {
    if (e instanceof ApiError) {
      console.error(`API ${e.status} – ${e.code}: ${e.message}`);
    }
    throw e;
  }
}
```

### React Query hooks for generation lifecycle

Leverage `useStartGeneration`, `useCancelGeneration`, and `useGeneration` to trigger mutations and keep cached data fresh.

```typescript
import { useStartGeneration, useCancelGeneration, useGeneration } from './api';

function GenerationPanel({ id }: { id: string }) {
  const { data: gen } = useGeneration(id);
  const start = useStartGeneration();
  const cancel = useCancelGeneration();

  return (
    <>
      <button onClick={() => start.mutate({ prompt: 'Hello' })}>Start</button>
      <button onClick={() => cancel.mutate(id)}>Cancel</button>
      <pre>{JSON.stringify(gen, null, 2)}</pre>
    </>
  );
}
```

## When to Use

- Fetching or mutating generation data from the `/api/generate` endpoints.  
- Populating provider lists or analytics dashboards with React Query.  
- Implementing global error boundaries that need HTTP status details.

## Commands

```bash
# Run the full stack locally
docker compose up --build

# Execute the CLI entry point
python -m repoforge.cli run
```

## Anti-Patterns

### Don't: swallow `ApiError` without handling status

Ignoring the structured error loses valuable debugging information.

```typescript
// BAD
await fetchApi('/api/providers'); // errors are silently ignored
```
<!-- L3:END -->