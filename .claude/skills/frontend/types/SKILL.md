---
name: define-types-model
description: >
  Defines core TypeScript types for generation workflow.
  Trigger: When the `types` module is imported or generation data structures are needed.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 120
dependencies: []
related_skills:
  - add-generation-endpoint
  - extend-user-model
load_priority: high
---

<!-- L1:START -->
# define-types-model

Defines the core TypeScript interfaces and enums used throughout the generation pipeline.

**Trigger**: When the `types` module is imported or generation data structures are needed.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create user type | `interface User { github_user_id: number; login: string; avatar_url: string; }` |
| Define generation mode | `type GenerationMode = 'docs' | 'skills' | 'both';` |
| Emit generation started event | `type GenerationStartedEvent = { type: 'generation_started'; generation_id: string; repo_url: string; mode: GenerationMode; };` |

## Critical Patterns (Summary)
- **Domain data structures**: Define `User` and `ProviderKey` interfaces to model external entities.
- **Typed generation enums & events**: Use `GenerationMode`, `GenerationStatus`, and `GenerationStartedEvent` for strict type safety.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Domain data structures (User, ProviderKey)

Model external entities with explicit interfaces to enable IDE autocomplete and runtime validation.

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

### Typed generation enums & events (GenerationMode, GenerationStatus, GenerationStartedEvent)

Leverage union types and discriminated event interfaces to enforce valid states and simplify switch‑case handling.

```typescript
export type GenerationMode = 'docs' | 'skills' | 'both';
export type GenerationStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface GenerationStartedEvent {
  type: 'generation_started';
  generation_id: string;
  repo_url: string;
  mode: GenerationMode;
}
```

## When to Use

- When building API payloads that include user or provider information.
- When handling generation lifecycle events in the frontend or SSE streams.
- When validating request bodies for generation jobs.

## Commands

```bash
# Run the Python CLI inside Docker
docker compose run --rm app python -m repoforge.cli generate --repo https://github.com/example/repo

# Rebuild containers after type changes
docker compose up --build -d
```

## Anti-Patterns

### Don't: Use loose string literals for generation mode

Using arbitrary strings defeats the purpose of the `GenerationMode` union and introduces runtime errors.

```typescript
// BAD
type BadMode = string; // loses type safety
const mode: BadMode = 'documentation'; // not part of the allowed set
```
<!-- L3:END -->