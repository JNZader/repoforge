---
name: generate-request-types
description: >
  This skill covers the generation of request and response types for user interactions.
  Trigger: Load this skill when defining types for generation requests and responses.
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
# generate-request-types

This skill covers the generation of request and response types for user interactions.

**Trigger**: Load this skill when defining types for generation requests and responses.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Define user generation request | `GenerateRequest` |
| Define user generation response | `GenerateResponse` |

## Critical Patterns (Summary)
- **GenerateRequest**: Defines the structure for a user generation request.
- **GenerateResponse**: Defines the structure for a user generation response.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### GenerateRequest

Defines the structure for a user generation request, including necessary parameters.

```typescript
// Example of a GenerateRequest type
const request: GenerateRequest = {
  userId: "12345",
  providerKey: ProviderKey.Google,
  mode: GenerationMode.Fast
};
```

### GenerateResponse

Defines the structure for a user generation response, detailing the outcome of the request.

```typescript
// Example of a GenerateResponse type
const response: GenerateResponse = {
  status: GenerationStatus.Success,
  data: {
    user: new User("John Doe", "john@example.com"),
    generationId: "67890"
  }
};
```

## When to Use

- When creating types for user generation requests in the frontend.
- When handling responses from user generation processes.

## Commands

```bash
docker-compose up
python repoforge/cli.py generate
```

## Anti-Patterns

### Don't: Use generic types

Using generic types can lead to unclear structures and unexpected behaviors.

```typescript
// BAD
const badRequest: any = {
  userId: "12345",
  providerKey: "Google",
  mode: "Fast"
};
```
<!-- L3:END -->