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
| Set API URL | `set-api-url` |
| Provide Auth Context | `provide-auth-context` |

## Critical Patterns (Summary)
- **Set API URL**: Define the base URL for API requests.
- **Provide Auth Context**: Wrap your application with the AuthProvider for authentication state management.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Set API URL

Define the base URL for API requests to ensure all authentication requests are directed correctly.

```typescript
const apiUrl = API_URL; // Use the exported API_URL for consistent API endpoint
```

### Provide Auth Context

Wrap your application with the AuthProvider to manage authentication state across components.

```typescript
import { AuthProvider } from './lib/auth';

const App = () => (
  <AuthProvider>
    {/* Your application components */}
  </AuthProvider>
);
```

## When to Use

- When setting up the authentication flow in your frontend application.
- When you need to manage user sessions and authentication state across multiple components.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Hardcode API URLs

Hardcoding API URLs can lead to maintenance issues and inconsistencies.

```typescript
// BAD
const apiUrl = 'http://localhost:3000/api'; // Avoid this practice
```
<!-- L3:END -->