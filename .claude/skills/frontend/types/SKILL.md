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
};
```

### GenerateResponse

Defines the structure for a generation response, including status and data.

```typescript
// Example of a GenerateResponse
const response: GenerateResponse = {
  status: GenerationStatus.Success,
  data: {
    id: '12345',
    result: 'Generated content here',
  },
};
```

## When to Use

- When creating a new generation request for a user.
- When processing the response from a generation event.

## Commands

```bash
python repoforge/cli.py generate
docker-compose up
```

## Anti-Patterns

### Don't: Use raw types

Using raw types instead of defined types can lead to inconsistencies and errors.

```typescript
// BAD
const request = {
  key: 'SomeKey',
  mode: 'Standard',
};
```
<!-- L3:END -->