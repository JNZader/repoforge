---
name: example-layer
description: > 
  This layer encapsulates the core business logic for the example domain.
  Trigger: When working in example/ — adding, modifying, or debugging core services.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
---

## Layer Structure

```
example/
├── service.ts — defines service interfaces
├── controller.ts — HTTP request handling
└── repository.ts — data persistence
```

## Critical Patterns

### Single Responsibility

Each file should expose a single cohesive concern.

```ts
export class ExampleService {
  // business methods
}
```

### Dependency Injection

```ts
export function createExampleController(service: ExampleService) {
  // controller logic
}
```

## When to Use

- Implementing new business operations
- Refactoring existing logic
- Integrating with other layers via defined interfaces

## Adding a New Service

1. Create `src/example/<Name>Service.ts`.
2. Export the class implementing the required interface.
3. Register it in the DI container (`src/example/index.ts`).
4. Run unit tests to verify behavior.

## Commands

```bash
npm run build --workspace=example
npm test --workspace=example
```

## Anti-Patterns

- **Don't**: Mix HTTP handling with business logic — breaks separation of concerns.
- **Don't**: Directly import repository in controller — bypasses service layer.

## Quick Reference

| Task | File | Pattern |
|------|------|---------|
| Add service | `src/example/MyService.ts` | `export class MyService` |