---
name: frontend-layer
description: >
  Frontend layer for the Gentleman-Skills project. Handles the React/TypeScript UI,
  including generation streaming, authentication, and component composition.
  Trigger: When working in apps/web/ — adding pages, debugging streaming, or
  modifying auth flows.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 650
  dependencies: []
  related_skills: [backend-layer, build_modules-layer]
  load_priority: high
---

<!-- L1:START -->
# frontend-layer

Frontend layer for Gentleman-Skills React/TypeScript UI. Covers generation streaming, auth, and component composition.

**Trigger**: When working in apps/web/ — adding pages, debugging streaming, or modifying auth flows.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add new page component | `apps/web/src/components/Layout.tsx` |
| Start generation stream | `useStartGeneration()` mutation |
| Check generation status | `useGenerationStream()` hook |

## Critical Patterns (Summary)
- **TypeScript React Components**: Functional components with hooks; all UI components use functional pattern with ReactNode children.
- **Generation Streaming Flow**: `useGenerationStream` hook + `startGeneration` mutation + SSE event polling pattern.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Pattern 1: Generation Streaming Flow

The `useGenerationStream` hook manages SSE-based generation state with steps tracking. Components subscribe via `useGenerationStream(generationId)` and render progress using the `steps` array and `progress` object. The `startGeneration` mutation triggers the backend flow and returns a `GenerateResponse`.

```typescript
// Use hook to track generation state
const { status, steps, progress } = useGenerationStream(generationId);

// Render progress UI
{steps.map((step) => (
  <div key={step.label}>
    {step.label}: {step.status}
  </div>
))}
```

### Pattern 2: Error Boundary + Auth Provider Pattern

`ErrorBoundary` wraps critical components to catch render errors without breaking the UI. `AuthProvider` must wrap the app tree and `useAuth` must be called within its context. API calls use `fetchApi` with proper `ApiError` handling for status codes.

```typescript
// ErrorBoundary wraps children to catch errors
<ErrorBoundary>
  <Suspense fallback={<LoadingSpinner />}>
    <PageContent />
  </Suspense>
</ErrorBoundary>

// Auth must wrap the tree
<AuthProvider>
  <App />
</AuthProvider>
```
<!-- L3:END -->

## When to Use

- Adding a new page or component under `apps/web/src/components/`
- Debugging generation streaming state or SSE connectivity
- Wrapping components with error boundaries or auth checks
- Modifying generation flow or API endpoints

## Commands

```bash
# Install deps
cd apps/web && npm install

# Run dev server
cd apps/web && npm run dev

# Build for production
cd apps/web && npm run build

# Run tests
cd apps/web && npm test
```

## Anti-Patterns

### Don't: Access API directly without `fetchApi` wrapper — `apps/web/src/lib/api.ts`

Direct `fetch` calls bypass error normalization, auth headers, and consistent error types (`ApiError`). Always use the exported `fetchApi`, `startGeneration`, and `streamGeneration` functions for consistent `ApiError` handling, automatic retries, and SSE streaming support.

```typescript
// BAD — bypasses error handling and auth
const resp = await fetch('/api/generate', { method: 'POST' });
const data = await resp.json();

// GOOD — uses typed error handling
const data = await startGeneration({ provider, key });
```
<!-- L3:END -->