---
name: generate-request-response
description: >
  This skill covers the generation of requests and responses in TypeScript.
  Trigger: Load this skill when working with types related to generation.
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
# generate-request-response

This skill covers the generation of requests and responses in TypeScript.

**Trigger**: Load this skill when working with types related to generation.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a generate request | `GenerateRequest` |
| Handle generation response | `GenerateResponse` |

## Critical Patterns (Summary)
- **GenerateRequest**: Defines the structure for a generation request.
- **GenerateResponse**: Defines the structure for a generation response.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### GenerateRequest

Defines the structure for a generation request, including necessary parameters.

```typescript
// Example of a GenerateRequest
const request: GenerateRequest = {
  providerKey: ProviderKey.SomeProvider,
  mode: GenerationMode.Standard,
  // additional properties
};
```

### GenerateResponse

Defines the structure for a generation response, including status and data.

```typescript
// Example of a GenerateResponse
const response: GenerateResponse = {
  status: GenerationStatus.Success,
  data: {
    // response data
  },
};
```

## When to Use

- When creating a new generation request in the frontend.
- When processing the response from a generation event.

## Commands

```bash
docker-compose up
python repoforge/cli.py generate
```

## Anti-Patterns

### Don't: Use incorrect types

Using incorrect types can lead to runtime errors and unexpected behavior.

```typescript
// BAD
const badRequest: GenerateRequest = {
  providerKey: "invalidKey", // should be of type ProviderKey
  mode: "invalidMode", // should be of type GenerationMode
};
```
<!-- L3:END -->