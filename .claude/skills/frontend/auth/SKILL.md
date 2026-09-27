---
name: add-auth-provider
description: >
  Patterns for integrating authentication context in a React frontend.
  Trigger: when auth utilities are imported or used.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 340
dependencies: []
related_skills:
  - add-react-context
  - configure-env-variables
load_priority: high
---

<!-- L1:START -->
# add-auth-provider

Provides a quick way to set up authentication context in the web app.

**Trigger**: when auth utilities are imported or used.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Wrap root with provider | `<AuthProvider>{children}</AuthProvider>` |
| Access auth state | `const auth = useAuth();` |
| Use API base URL | `fetch(API_URL + '/endpoint')` |

## Critical Patterns (Summary)
- **AuthProvider**: supply React context for auth.
- **useAuth**: safely consume the auth context.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### AuthProvider – expose authentication via React context

Wrap your application (or part of it) with `AuthProvider` so child components can access auth data.

```typescript
import { AuthProvider } from './lib/auth';

function Root() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}
```

### useAuth – retrieve authentication state inside components

Call `useAuth` only inside components that are descendants of `AuthProvider` to get the typed auth context.

```typescript
import { useAuth } from './lib/auth';

function Dashboard() {
  const { user, token } = useAuth(); // AuthContextValue
  return <div>Welcome, {user.name}</div>;
}
```

## When to Use

- When you need a global auth state across multiple pages.
- When a component must read the current user or token.
- When you want to centralize API URL handling with `API_URL`.

## Commands

```bash
docker compose up --build          # rebuild and run the dev container
python -m repoforge.cli            # run the repository CLI
```

## Anti-Patterns

### Don't: Call useAuth outside an AuthProvider

Using the hook without the provider throws an error and breaks the component tree.

```typescript
import { useAuth } from './lib/auth';

function Orphan() {
  // BAD: no AuthProvider above this component
  const auth = useAuth(); // throws Error
  return <div>{auth?.user?.name}</div>;
}
```
<!-- L3:END -->