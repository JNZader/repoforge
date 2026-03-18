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
- **Manage stream status**: Utilize `StreamStatus` to track the state of the generation stream.
- **Handle step items**: Use `StepItem` to represent individual steps in the generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Manage stream status

Utilize `StreamStatus` to track the state of the generation stream, allowing for responsive UI updates.

```typescript
import { StreamStatus } from '@/hooks/useGenerationStream';

const status: StreamStatus = StreamStatus.RUNNING; // Example usage
```

### Handle step items

Use `StepItem` to represent individual steps in the generation process, enabling detailed tracking of progress.

```typescript
import { StepItem } from '@/hooks/useGenerationStream';

const step: StepItem = { id: 1, description: 'Step 1 description' }; // Example usage
```

## When to Use

- When implementing a generation stream in a React component.
- When needing to track the progress of a multi-step generation process.

## Commands

```bash
docker-compose up
python repoforge/cli.py
```

## Anti-Patterns

### Don't: Ignore stream state management

Neglecting to manage stream states can lead to unresponsive UI and poor user experience.

```typescript
// BAD
const status = StreamStatus.IDLE; // Not updating based on actual stream state
```
<!-- L3:END -->