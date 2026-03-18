---
name: use-auth-provider
description: >
  This skill covers patterns for implementing authentication in a frontend application.
  Trigger: Load this skill when managing user authentication.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 250
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# use-auth-provider

This skill covers patterns for implementing authentication in a frontend application.

**Trigger**: Load this skill when managing user authentication.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Set API URL for auth | `set-api-url` |
| Provide authentication context | `provide-auth-context` |

## Critical Patterns (Summary)
- **Set API URL for auth**: Define the API endpoint for authentication.
- **Provide authentication context**: Wrap your application with the AuthProvider for context access.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Set API URL for auth

Define the API endpoint for authentication using the exported `API_URL`.

```typescript
const apiUrl = API_URL; // Set the API URL for authentication
```

### Provide authentication context

Wrap your application with the `AuthProvider` to provide authentication context to components.

```typescript
import { AuthProvider } from './lib/auth';

const App = () => (
  <AuthProvider>
    {/* Your application components */}
  </AuthProvider>
);
```

## When to Use

- When you need to set the API URL for authentication requests.
- When wrapping components to provide authentication context.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Hardcode API URLs

Hardcoding API URLs can lead to maintenance issues and environment-specific bugs.

```typescript
const apiUrl = 'http://localhost:3000/api/auth'; // BAD
```
<!-- L3:END -->