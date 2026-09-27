---
name: add-types-definitions
description: >
  Provides core TypeScript type definitions for generation workflow.
  Trigger: when working with `types` in the web frontend.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - define-user-model
  - handle-generation-events
load_priority: high
---

<!-- L1:START -->
# add-types-definitions

Adds essential TypeScript interfaces and union types for the generation system.

**Trigger**: loading the `types` module in the web layer.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define user data | `interface User { … }` |
| Set generation mode | `type GenerationMode = 'docs' | 'skills' | 'both'` |
| Listen for start event | `interface GenerationStartedEvent extends GenerationSSEEvent { … }` |

## Critical Patterns (Summary)
- **User & ProviderKey definitions**: model authenticated users and their keys.
- **Generation enums & events**: type‑safe handling of modes, statuses, and SSE events.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User & ProviderKey definitions

Model the authenticated GitHub user and associated provider keys with strict typings to avoid runtime mismatches.

```typescript
export interface User {
  github_user_id: number;
  login: string;
  avatar_url: string;
}

export interface ProviderKey {
  provider: string;
  key_hint: string | null;
  validated_at: string | null;
  status?: string;
  note?: string;
  storage?: 'persistent' | 'session';
}
```

### Generation enums & events

Use `GenerationMode` and `GenerationStatus` unions for compile‑time safety, and extend `GenerationSSEEvent` for specific SSE payloads like `GenerationStartedEvent`.

```typescript
export type GenerationMode = 'docs' | 'skills' | 'both';
export type GenerationStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface GenerationStartedEvent extends GenerationSSEEvent {
  type: 'generation_started';
  generation_id: string;
  repo_url: string;
  mode: GenerationMode;
}
```

## When to Use

- When building API request payloads for `/generate` endpoints.
- When rendering UI components that depend on user authentication or generation progress.
- When debugging SSE streams from the backend generation service.

## Commands

```bash
# Run the Python CLI inside Docker
docker compose run --rm web python -m repoforge.cli generate --repo https://github.com/example/repo

# Start the full stack locally
docker compose up -d
```

## Anti-Patterns

### Don't: treat union types as arbitrary strings

Casting a string to a union bypasses type safety and can cause runtime errors.

```typescript
// BAD
const userInput: string = getUserInput();
const mode: GenerationMode = userInput as GenerationMode; // unsafe
```
<!-- L3:END -->