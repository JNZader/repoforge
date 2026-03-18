---
name: use-auth
description: >
  This skill covers authentication patterns using the AuthProvider and useAuth hooks.
  Trigger: Load this skill when implementing authentication in the frontend.
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
# use-auth

This skill covers authentication patterns using the AuthProvider and useAuth hooks.

**Trigger**: Load this skill when implementing authentication in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Set API URL | `set-api-url` |
| Provide Auth Context | `provide-auth-context` |

## Critical Patterns (Summary)
- **Set API URL**: Define the API_URL for authentication requests.
- **Provide Auth Context**: Use AuthProvider to wrap your application for authentication state management.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Set API URL

Define the API_URL for authentication requests to ensure the application communicates with the correct backend.

```typescript
const apiUrl = API_URL; // Set the API URL for authentication
```

### Provide Auth Context

Use AuthProvider to wrap your application, allowing access to authentication state throughout the component tree.

```typescript
import { AuthProvider } from './lib/auth';

const App = () => (
  <AuthProvider>
    {/* Other components */}
  </AuthProvider>
);
```

## When to Use

- When setting up authentication for a new frontend application.
- When needing to manage user authentication state across multiple components.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Hardcode API URLs

Hardcoding API URLs can lead to maintenance issues and environment-specific bugs.

```typescript
const apiUrl = 'http://localhost:3000/api'; // BAD
```
<!-- L3:END -->