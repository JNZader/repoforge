---
name: add-types-endpoint
description: >
  Type-safe frontend types for generation workflows and SSE events.
  Trigger: when adding new generation types or SSE event handlers.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 650
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# add-types-endpoint

Type-safe frontend types for generation workflows and SSE events.

**Trigger**: when adding new generation types or SSE event handlers.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Validate User type | `User` |
| Handle Generation events | `GenerationEvent` |
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns

### Pattern: User Type Validation

Validate authenticated user identity using the `User` interface for API responses and session storage.

```typescript
import { User } from '@/lib/types';

function getDisplayName(user: User): string {
  return user.login;
}
```

### Pattern: Generation Mode Dispatch

Switch on `GenerationMode` to route generation requests to the correct workflow path.

```typescript
import { GenerationMode } from '@/lib/types';

function routeGeneration(mode: GenerationMode): void {
  switch (mode) {
    case 'docs':
      // docs-only path
      break;
    case 'skills':
      // skills-only path
      break;
    case 'both':
      // combined path
      break;
  }
}
```

## When to Use

- Creating new generation request handlers
- Processing SSE event streams for generation progress
- Validating user authentication state

## Commands

```bash
docker build -t repoforge/app .
python repoforge/cli.py --help
```

## Anti-Patterns

### Don't: Omit optional ProviderKey fields

Accessing `provider` or `key_hint` without checking for `null` causes runtime errors when credentials are incomplete.

```typescript
import { ProviderKey } from '@/lib/types';

// BAD - assumes key_hint is always present
const hint = providerKey.key_hint; // TypeError if null

// GOOD - handle optional field
const hint = providerKey.key_hint ?? 'no key set';
```
<!-- L3:END -->