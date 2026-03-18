---
name: add-auth-provider
description: >
  This skill covers patterns for integrating authentication in the frontend.
  Trigger: When implementing user authentication in the application.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: low
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-auth-provider

This skill covers patterns for integrating authentication in the frontend.

**Trigger**: When implementing user authentication in the application.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Set API URL for auth | `API_URL` |
| Provide auth context | `AuthProvider` |
| Use authentication hooks | `useAuth` |

## Critical Patterns (Summary)
- **Set API URL for auth**: Define the API endpoint for authentication.
- **Provide auth context**: Wrap your application with the AuthProvider for context.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Set API URL for auth

Define the API endpoint for authentication to ensure all requests are directed correctly.

```typescript
const apiUrl = API_URL; // Use the exported API_URL for authentication requests
```

### Provide auth context

Wrap your application with the AuthProvider to provide authentication context to all components.

```typescript
import { AuthProvider } from './lib/auth';

const App = () => (
  <AuthProvider>
    {/* Other components */}
  </AuthProvider>
);
```

## When to Use

- When setting up user authentication in a new frontend application.
- When needing to manage user sessions and authentication state across components.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Hardcode API URLs

Hardcoding API URLs can lead to maintenance issues and security vulnerabilities.

```typescript
const apiUrl = 'http://localhost:3000/api/auth'; // BAD
```
<!-- L3:END -->