---
name: usegenerationstream-hook
description: >
  This skill covers the usage of the `useGenerationStream` hook for managing streaming states.
  Trigger: Load this skill when implementing streaming functionality in the frontend.
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
# usegenerationstream-hook

This skill covers the usage of the `useGenerationStream` hook for managing streaming states.

**Trigger**: Load this skill when implementing streaming functionality in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Manage stream status | `useGenerationStream` |
| Define step items | `StepItem` |

## Critical Patterns (Summary)
- **Manage stream status**: Utilize `useGenerationStream` to handle the streaming state.
- **Define step items**: Create and manage individual steps using `StepItem`.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Manage stream status

Utilize `useGenerationStream` to handle the streaming state effectively, allowing for real-time updates.

```typescript
import { useGenerationStream, StreamStatus } from '@/hooks/useGenerationStream';

const MyComponent = () => {
  const { status } = useGenerationStream();

  if (status === StreamStatus.Loading) {
    return <LoadingSpinner />;
  }
  return <div>Stream is ready!</div>;
};
```

### Define step items

Create and manage individual steps using `StepItem`, which helps in organizing the streaming process.

```typescript
import { StepItem } from '@/hooks/useGenerationStream';

const steps: StepItem[] = [
  { id: 1, title: 'Step 1', completed: false },
  { id: 2, title: 'Step 2', completed: true },
];
```

## When to Use

- When implementing a real-time data streaming feature in your application.
- When you need to manage multiple steps in a streaming process.

## Commands

```bash
docker-compose up
python repoforge/cli.py run
```

## Anti-Patterns

### Don't: Ignore stream status

Ignoring the stream status can lead to a poor user experience and unhandled states.

```typescript
// BAD
const { status } = useGenerationStream();
// No handling of status
```
<!-- L3:END -->