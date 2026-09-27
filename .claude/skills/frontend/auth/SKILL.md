---
name: add-auth-provider
description: >
  Provides patterns for integrating AuthProvider and useAuth in a React app.
  Trigger: when auth context is needed in the UI.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - configure-api-url
  - manage-auth-context
load_priority: high
---

<!-- L1:START -->
# add-auth-provider

Provides concise patterns to initialize and consume authentication in the frontend.

**Trigger**: when auth context is needed in the UI.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Wrap root with provider | `<AuthProvider>{children}</AuthProvider>` |
| Access auth state | `const auth = useAuth();` |
| Read API base URL | `const base = API_URL;` |

## Critical Patterns (Summary)
- **Wrap Application with AuthProvider**: Enclose the app tree in `<AuthProvider>` to supply auth context.
- **Consume Auth State via useAuth**: Call `useAuth()` inside components to get the current auth value.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Wrap Application with AuthProvider

Place `AuthProvider` at the top level (e.g., in `App.tsx`) so all descendants can access authentication data.

```typescript
import { AuthProvider } from './lib/auth';
import { Layout } from './components/Layout';

function App() {
  return (
    <AuthProvider>
      <Layout />
    </AuthProvider>
  );
}
```

### Consume Auth State via useAuth

Use the `useAuth` hook inside any component that is a descendant of `AuthProvider` to retrieve the `AuthContextValue`. It throws if used outside the provider.

```typescript
import { useAuth } from './lib/auth';

function UserBadge() {
  const { user, token } = useAuth(); // AuthContextValue
  return <span>{user?.name ?? 'Guest'}</span>;
}
```

## When to Use

- When you need to protect routes or display user‑specific UI.
- When making API calls that require the `API_URL` and auth token.
- To debug missing context errors during development.

## Commands

```bash
# Rebuild and run the Docker environment
docker compose up --build

# Execute the repository CLI (Python entry point)
python -m repoforge.cli
```

## Anti-Patterns

### Don't: Call useAuth outside AuthProvider

Calling `useAuth` in a component that isn’t wrapped by `AuthProvider` triggers a runtime error.

```typescript
import { useAuth } from './lib/auth';

function OrphanComponent() {
  // BAD: No AuthProvider above this component
  const auth = useAuth(); // throws Error
  return <div>{auth?.user?.name}</div>;
}
```
<!-- L3:END -->