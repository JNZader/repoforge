---
name: usegenerationstream-hook
description: >
  This skill covers patterns for managing generation streams in a React application.
  Trigger: Load when using `useGenerationStream` for stream management.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# usegenerationstream-hook

This skill covers patterns for managing generation streams in a React application.

**Trigger**: Load when using `useGenerationStream` for stream management.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Manage stream status | `StreamStatus` |
| Handle step items | `StepItem` |

## Critical Patterns (Summary)
- **StreamStatus**: Use to represent the current status of the generation stream.
- **StepItem**: Utilize for managing individual steps in the generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### StreamStatus

Use `StreamStatus` to represent the current status of the generation stream, allowing for effective state management.

```typescript
import { StreamStatus } from '@/hooks/useGenerationStream';

const status: StreamStatus = StreamStatus.RUNNING;
```

### StepItem

Utilize `StepItem` for managing individual steps in the generation process, ensuring each step is tracked correctly.

```typescript
import { StepItem } from '@/hooks/useGenerationStream';

const step: StepItem = { id: 1, description: 'Initializing...' };
```

## When to Use

- When managing the state of a generation stream in a React component.
- When tracking individual steps of a process in a user interface.

## Commands

```bash
docker-compose up
python repoforge/cli.py
```

## Anti-Patterns

### Don't: Use hardcoded statuses

Hardcoding statuses can lead to inconsistencies and make the code less maintainable.

```typescript
// BAD
const status = 'RUNNING'; // Avoid this
```
<!-- L3:END -->