---
name: generate-request-types
description: >
  This skill covers the creation and management of generation request types.
  Trigger: Load this skill when working with types related to generation requests.
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
# Generate Request Types

This skill covers the creation and management of generation request types.

**Trigger**: Load this skill when working with types related to generation requests.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Create a user type | `User` |
| Define generation mode | `GenerationMode` |

## Critical Patterns (Summary)
- **User**: Defines the structure for user-related data.
- **GenerationMode**: Specifies the mode of generation for requests.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User

Defines the structure for user-related data, encapsulating user attributes.

```typescript
// Example of User type usage
const newUser: User = {
  id: '123',
  name: 'John Doe',
  email: 'john@example.com'
};
```

### GenerationMode

Specifies the mode of generation for requests, allowing for different generation strategies.

```typescript
// Example of GenerationMode usage
const mode: GenerationMode = GenerationMode.AUTOMATIC;
```

## When to Use

- When defining user data structures in your application.
- When specifying how generation requests should be processed.

## Commands

```bash
docker-compose up
python repoforge/cli.py generate
```

## Anti-Patterns

### Don't: Use generic types

Using overly generic types can lead to confusion and errors in type safety.

```typescript
// BAD
const genericUser: any = {};
```
<!-- L3:END -->