---
name: frontend-layer
description: >
  Frontend layer owns the React UI, routing, and client‑side data fetching for the web app.
  Trigger: When working in frontend/ directory — adding, modifying, or debugging UI components and hooks.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 1200
dependencies: []
related_skills: [backend-layer, build_modules-layer]
load_priority: high
---

<!-- L1:START -->
# frontend-layer

Provides the React entry point, layout, protected routing, and all client‑side API hooks.

**Trigger**: When working in `frontend/` directory — adding, modifying, or debugging UI components, routes, or data‑fetch hooks.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task                     | Pattern |
|--------------------------|---------|
| Add a new protected page| `ProtectedRoute` |
| Fetch generation data   | `useGeneration(id)` |
| Show loading state      | `LoadingSpinner` |

## Critical Patterns (Summary)
- **React Query Data Hooks**: All server data accessed via the `use*` hooks in `src/lib/api.ts`.
- **Error Boundary Wrapping**: Wrap lazy routes with `ErrorBoundary` and fallback to `LoadingSpinner`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### React Query Data Hooks

All asynchronous server interactions are encapsulated in custom React Query hooks (`useGeneration`, `useStartGeneration`, `useAnalyticsUsage`, etc.). This centralises caching, error handling, and invalidation.

```tsx
import { useGeneration } from '@/lib/api';

export function GenerationDetail({ id }: { id: string }) {
  const { data, isLoading, error } = useGeneration(id);
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorBoundary error={error} />;
  return <div>{data?.status}</div>;
}
```

### Error Boundary Wrapping

UI entry points must be wrapped with `ErrorBoundary` to catch render errors and display a graceful fallback. Combine with `Suspense` for lazy loading.

```tsx
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import { HashRouter } from 'react-router-dom';

export function App() {
  return (
    <HashRouter>
      <ErrorBoundary>
        <Suspense fallback={<LoadingSpinner />}>
          {/* routes */}
        </Suspense>
      </ErrorBoundary>
    </HashRouter>
  );
}
```

## When to Use

- Rendering a page that requires authentication – use `ProtectedRoute` together with `useAuth`.
- Displaying generation progress – combine `useGenerationStream` with `LoadingSpinner`.
- Integrating a new backend endpoint – create a corresponding `use*` hook in `src/lib/api.ts`.

## Commands

```bash
npm ci            # install exact dependencies
npm run dev       # start Vite dev server (default port 3000)
docker compose up # spin up backend services for integration testing
```

## Anti-Patterns

### Don't: Call `fetchApi` directly inside components

By bypassing the React Query hooks you lose caching, automatic retries, and query invalidation, leading to stale UI and duplicated network traffic.

```tsx
// BAD
export function BadComponent({ id }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetchApi(`/api/generate/${id}`).then(setData);
  }, [id]);
  // …
}
```
<!-- L3:END -->