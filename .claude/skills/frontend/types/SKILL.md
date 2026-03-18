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
| Define a user type | `User` |
| Create a generation request | `GenerateRequest` |

## Critical Patterns (Summary)
- **User Type Definition**: Defines the structure of a user object.
- **Generation Request Creation**: Handles the creation of a generation request object.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### User Type Definition

Defines the structure of a user object, which is essential for managing user data in the application.

```typescript
// Example of User type
export type User = {
  id: string;
  name: string;
  email: string;
};
```

### Generation Request Creation

Handles the creation of a generation request object, which is used to initiate a generation process.

```typescript
// Example of GenerateRequest type
export type GenerateRequest = {
  userId: string;
  mode: GenerationMode;
  parameters: Record<string, any>;
};
```

## When to Use

- When defining user-related data structures in the frontend.
- When creating requests for generation processes in the application.

## Commands

```bash
docker-compose up
python repoforge/cli.py generate
```

## Anti-Patterns

### Don't: Use Inconsistent Type Definitions

Inconsistent type definitions can lead to runtime errors and confusion in the codebase.

```typescript
// BAD
export type User = {
  id: number; // Inconsistent type
  name: string;
  email: string;
};
```
<!-- L3:END -->