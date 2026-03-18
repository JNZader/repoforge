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
  token_estimate: 350
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
| Use Auth Provider | `use-auth-provider` |

## Critical Patterns (Summary)
- **Set API URL**: Define the base URL for API requests.
- **Use Auth Provider**: Wrap your application with the AuthProvider for authentication context.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Set API URL

Define the base URL for API requests to ensure all authentication requests are directed correctly.

```typescript
const apiUrl = API_URL; // Use the exported API_URL for consistent API endpoint
```

### Use Auth Provider

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

- When setting up the authentication layer in your frontend application.
- When you need to provide authentication context to child components.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Hardcode API URLs

Hardcoding API URLs can lead to maintenance issues and inconsistencies.

```typescript
const apiUrl = 'http://localhost:3000/api'; // BAD
```
<!-- L3:END -->