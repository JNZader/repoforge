---
name: add-types-definitions
description: >
  Provides patterns for defining core TypeScript types used across the web frontend.
  Trigger: types
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
complexity: low
token_estimate: 350
dependencies: []
related_skills:
  - type-safe-api
  - frontend-models
load_priority: high
---

<!-- L1:START -->
# add-types-definitions

Defines reusable TypeScript types for users, providers, and generation workflows.

**Trigger**: When working with the `types` module.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define a user model | `type User = { id: string; name: string; email?: string };` |
| Enumerate generation modes | `enum GenerationMode { TEXT = "text", IMAGE = "image" }` |
| Shape a generate request | `interface GenerateRequest { prompt: string; mode: GenerationMode; }` |

## Critical Patterns (Summary)
- **Define Strongly Typed Generation Enums**: Use `enum` for `GenerationMode` and `GenerationStatus`.
- **Structure API Payload Types**: Model `GenerateRequest` and `GenerateResponse` with explicit fields.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Define Strongly Typed Generation Enums

Export enums to guarantee valid mode and status values throughout the app.

```typescript
export enum GenerationMode {
  TEXT = "text",
  IMAGE = "image",
  AUDIO = "audio",
}

export enum GenerationStatus {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
}
```

### Structure API Payload Types

Create precise request/response interfaces that reference the enums above, avoiding loose `any` types.

```typescript
export interface GenerateRequest {
  prompt: string;
  mode: GenerationMode;
  provider?: ProviderKey;
}

export interface GenerateResponse {
  id: string;
  status: GenerationStatus;
  result?: string; // populated when status === COMPLETED
}
```

## When to Use

- When adding new endpoints that accept generation parameters.
- When extending the UI to display generation status or results.
- When refactoring loosely‑typed payloads to improve IDE autocomplete and runtime safety.

## Commands

```bash
# Run the Python CLI inside Docker
docker compose run --rm app python -m repoforge.cli

# Rebuild the frontend container after type changes
docker compose build web
```

## Anti-Patterns

### Don't: Use `any` for API payloads

Using `any` defeats TypeScript’s safety guarantees and leads to runtime errors.

```typescript
// BAD
export interface GenerateRequest {
  prompt: any;          // loses type checking
  mode: any;            // any value accepted
}
```
<!-- L3:END -->