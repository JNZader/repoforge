---
name: add-auth-provider
description: >
  Provides patterns for integrating the AuthProvider and useAuth hook in a React frontend.
  Trigger: auth
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - add-auth-context
  - handle-auth-errors
load_priority: high
---

<!-- L1:START -->
# add-auth-provider

Integrates authentication context and hook into the React app.

**Trigger**: auth
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Wrap root with provider | `<AuthProvider apiUrl={API_URL}>` |
| Access auth state | `const { user, login, logout } = useAuth();` |
| Check loading | `if (auth.loading) return <LoadingSpinner/>;` |

## Critical Patterns (Summary)
- **Provide Auth Context**: Use `