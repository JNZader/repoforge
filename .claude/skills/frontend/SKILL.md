---
name: frontend-layer
description: >
  The frontend layer owns the React UI, routing, and client‑side data fetching for the web app.
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

Provides the React entry point, layout, routing, auth, and API hooks for the web client.

**Trigger**: Changes inside `frontend/` (i.e., `apps/web/`) such as UI components, routes, or data‑fetching hooks.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Add a new page component | `export function NewPage() { … }` |
| Protect a route | `<ProtectedRoute>…</ProtectedRoute>` |
| Fetch data with hook | `useQuery({ queryKey: ['...'], queryFn: fetchApi })` |

## Critical Patterns (Summary)
- **Component Composition**: Wrap UI in `<ErrorBoundary>` and `<Suspense>` with `<LoadingSpinner>` as fallback.
- **React Query Integration**: Use