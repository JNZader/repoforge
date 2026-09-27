---
name: add-auth-context
description: >
  Configure authentication context and API endpoints for the application.
  Trigger: when setting up auth provider or configuring API_URL.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 450
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-auth-context

Configure authentication context and API endpoints for the application.

**Trigger**: when setting up AuthProvider or configuring API_URL.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Setup auth context | `<AuthProvider>` |
| Get API URL | `API_URL` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Summary)

### Pattern 1: AuthProvider Setup

Wrap the app shell with `AuthProvider` to enable `useAuth` hooks. This provider manages authentication state and must wrap all routes that need auth checks.

```typescript
import { AuthProvider } from '@/lib/auth';

<AuthProvider>
  <App />
</AuthProvider>
```
### Pattern 2: useAuth Hook

Call `useAuth()` to access the authentication context. It throws if used outside an `AuthProvider`, ensuring proper placement.

```typescript
const { user, login, logout } = useAuth();
```
## When to Use

- Setting up new application routes requiring authentication
- Accessing user session data in components
- Debugging auth state not propagating correctly

## Commands

```bash
docker build -t app:latest .
python -m repoforge.cli auth:status
```
## Anti-Patterns

### Don't: useAuth outside AuthProvider

Calling `useAuth()` without wrapping the component tree in `AuthProvider` throws `'useAuth must be used within an AuthProvider'`. Always ensure the provider is an ancestor in the component tree.

```typescript
// BAD: will throw error
const { user } = useAuth();
```
## Quick Reference

| Task | Pattern |
|------|---------|
| Setup auth context | `<AuthProvider>` |
| Get API URL | `API_URL` |
| Access user session | `useAuth()` |
<!-- L3:END -->