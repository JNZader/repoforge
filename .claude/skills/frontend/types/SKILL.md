---
name: generate-request-types
description: >
  This skill covers the generation of request and response types for user interactions.
  Trigger: Load this skill when working with types related to user generation requests.
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

**Trigger**: Load this skill when working with types related to user generation requests.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a user generation request | `GenerateRequest` |
| Handle user generation response | `GenerateResponse` |

## Critical Patterns (Summary)
- **GenerateRequest**: Defines the structure for user generation requests.
- **GenerateResponse**: Specifies the format for responses after user generation.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### GenerateRequest

Defines the structure for user generation requests, ensuring all necessary fields are included.

```typescript
// Example of a user generation request
const request: GenerateRequest = {
  userId: "12345",
  providerKey: ProviderKey.Google,
  generationMode: GenerationMode.Instant
};
```

### GenerateResponse

Specifies the format for responses after user generation, including status and data.

```typescript
// Example of a user generation response
const response: GenerateResponse = {
  status: GenerationStatus.Success,
  data: {
    user: new User("12345", "John Doe"),
    event: GenerationEvent.UserCreated
  }
};
```

## When to Use

- When creating a new user and needing to structure the request.
- When processing the response from a user generation API.

## Commands

```bash
python repoforge/cli.py generate-user
docker-compose up
```

## Anti-Patterns

### Don't: Use unstructured requests

Using unstructured requests can lead to errors and inconsistencies in data handling.

```typescript
// BAD
const badRequest = {
  id: "12345",
  mode: "instant"
};
```
<!-- L3:END -->